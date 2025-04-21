"""Instrumentation class for the Anthropic SDK."""
from typing import List, Optional
from datetime import datetime, timezone
from dataclasses import asdict
import platform
import sys
import os

import wrapt

from ._base import BaseInstrumentor
from .._utils import get_module_version, is_module_version_more_than
from ..logger import logger
from ..schemas import (
    SessionActionKind,
    SessionActionError,
    SessionActionRequest,
    SessionActionScanner,
)


class AnthropicInstrumentation(BaseInstrumentor):
    """Instrumentation class for Anthropic SDK."""

    def supports(self) -> bool:
        """Check if the Anthropic SDK is supported."""
        try:
            import anthropic
            version_correct = is_module_version_more_than("anthropic", "0.3.0")
            return version_correct if version_correct is not None else False
        except ImportError:
            logger.warning("Anthropic SDK not installed")
            return False

    def instrument(self):
        """Instrument the Anthropic SDK."""
        try:
            self._instrument_message_create()
            self._instrument_tool_results()
            # self._instrument_embedding()
        except Exception as e:
            logger.error(f"Failed to instrument Anthropic SDK: {str(e)}")
            raise

 
    def _extract_session_id(self, kwargs: dict) -> Optional[str]:
        """Extract session ID from the provided headers."""
        headers = kwargs.get("extra_headers", {})
        if "Layer-Session-Id" in headers:
            return headers.get("Layer-Session-Id")
        return headers.get("X-Layer-Session-Id")

    def _create_or_append(
        self,
        session_id: Optional[str],
        actions: List[SessionActionRequest],
    ) -> str:
        """Create or append a session in Layer."""
        if session_id:
            for action in actions:
                self._layer.append_action(
                    session_id,
                    **asdict(action),
                )
                logger.debug(f"Appended {action.kind.value} action to '{session_id}' session")
            return session_id

        logger.debug(f"No session ID provided. Creating a new session with {len(actions)} actions")

        # Get metadata from the first action's attributes
        first_action_attrs = actions[0].attributes if actions else {}
        headers = first_action_attrs.get("extra_headers", {})

        new_session_id = self._layer.create_session(
            # attributes=metadata,
            actions=actions,
        )
        return new_session_id

    def _process_completion_stream(self, session_id, start_time, result, model=None):
        """Process streaming responses."""
        completion_content = ""
        chunk_count = 0
        
        for event in result:
            if hasattr(event, 'type'):
                if event.type == "content_block_delta":
                    if event.delta.text:
                        completion_content += event.delta.text
                        chunk_count += 1
            
            yield event

        self._create_or_append(session_id, [
            SessionActionRequest(
                kind=SessionActionKind.COMPLETION_OUTPUT,
                start_time=start_time,
                end_time=datetime.now(timezone.utc),
                attributes={
                    "stream": True,
                    "model.id": model,
                    "chunk_count": chunk_count,
                },
                data={
                    "messages": [
                        {
                            "content": completion_content,
                            "role": "assistant",
                        }
                    ],
                },
            )
        ])

    def _instrument_message_create(self):
        """Instrument the message creation method."""
        logger.debug("Setting up Anthropic message creation instrumentation")
        
        @wrapt.patch_function_wrapper('anthropic', 'Client')
        def wrap_client(wrapped, instance, args, kwargs):
            logger.debug("Initializing wrapped Anthropic Client")
            client = wrapped(*args, **kwargs)
            original_create = client.messages.create

            def wrapped_create(*args, **kwargs):
                start_time = datetime.now(timezone.utc)
                logger.debug("Intercepted Anthropic message creation")

                # Extract metadata from headers
                extra_headers = kwargs.get("extra_headers", {})
                
                # Extract and format messages
                messages = kwargs.get("messages", [])
                system = kwargs.get("system", "")
                
                if isinstance(messages, dict):
                    messages = [messages]
                
                formatted_messages = [
                    {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                    }
                    for msg in messages
                ]

                if system:
                    formatted_messages.insert(0, {
                        "role": "system",
                        "content": system
                    })

                # Prepare attributes with correct types
                attrs = {
                    "model.id": kwargs.get("model"),
                    "model.stream": kwargs.get("stream", False),  # Boolean
                    "model.max_tokens": int(kwargs.get("max_tokens", 1024)),  # Integer
                    "model.temperature": float(kwargs.get("temperature", 1.0)),  # Float
                    "model.top_p": float(kwargs.get("top_p", 1.0)),  # Float
                    "extra_headers": extra_headers,
                }

                # Create session with prompt
                try:
                    session_id = self._create_or_append(self._extract_session_id(kwargs), [
                        SessionActionRequest(
                            kind=SessionActionKind.COMPLETION_PROMPT,
                            start_time=start_time,
                            end_time=datetime.now(timezone.utc),
                            attributes=attrs,
                            data={"messages": formatted_messages},
                        )
                    ])
                    logger.debug(f"Created session {session_id} for completion prompt")

                    result = original_create(*args, **kwargs)
                    logger.debug("Successfully called Anthropic API")

                    # Handle streaming response
                    if kwargs.get("stream", False):
                        return self._process_completion_stream(
                            session_id, start_time, result, kwargs.get("model")
                        )

                    # Process normal response
                    content = getattr(result, 'content', None)
                    if isinstance(content, list) and len(content) > 0:
                        content = content[0].text

                    # Create completion output action
                    completion_action = SessionActionRequest(
                        kind=SessionActionKind.COMPLETION_OUTPUT,
                        start_time=start_time,
                        end_time=datetime.now(timezone.utc),
                        attributes=attrs,
                        data={
                            "messages": [
                                {
                                    "content": content,
                                    "role": "assistant",
                                }
                            ],
                        }
                    )

                    # Add usage information if available
                    if hasattr(result, "usage"):
                        completion_action.scanners = [
                            SessionActionScanner(
                                name="usage",
                                data={
                                    "input_tokens": getattr(result.usage, "input_tokens", 0),
                                    "output_tokens": getattr(result.usage, "output_tokens", 0),
                                    "total_tokens": getattr(result.usage, "total_tokens", 0),
                                },
                            )
                        ]

                    self._create_or_append(session_id, [completion_action])
                    logger.debug(f"Recorded completion output for session {session_id}")
                    
                    return result

                except Exception as e:
                    logger.error(f"Error in Anthropic message creation: {str(e)}")
                    if 'session_id' in locals():
                        self._create_or_append(
                            session_id,
                            [SessionActionRequest(
                                kind=SessionActionKind.COMPLETION_OUTPUT,
                                start_time=start_time,
                                end_time=datetime.now(timezone.utc),
                                error=SessionActionError(message=str(e))
                            )]
                        )
                    raise

            # Replace the create method
            client.messages.create = wrapped_create
            return client
        
# Adding Tools instrumentation
    def _instrument_tools(self):
        """Instrument the tools functionality."""
        @wrapt.patch_function_wrapper('openai.resources.chat.completions', 'Completions.create')
        def wrapper_for_tools(wrapped, instance, args, kwargs):
            # Check if the request includes tools
            if "tools" in kwargs and kwargs["tools"]:
                # Extract tool-specific data and process it
                # ...
                
                # Create a session action
                self._create_or_append(self._extract_session_id(kwargs), [
                    SessionActionRequest(
                        kind=SessionActionKind.TOOLS,
                        start_time=datetime.now(timezone.utc),
                        end_time=datetime.now(timezone.utc),
                        attributes={
                            "source": "openai",
                            "model.id": kwargs.get("model", ""),
                        },
                        data={
                            "tools": kwargs.get("tools", []),
                            "tool_choice": kwargs.get("tool_choice", None),
                        },
                    )
                ])
            
        # Call the original function
        result = wrapped(*args, **kwargs)
        
        # Process the result for tool calls if needed
        # ...
        
        return result
    
    def _instrument_message_create(self):
        """Instrument the message creation method."""
    
        @wrapt.patch_function_wrapper('anthropic', 'Client', 'messages.create')
        def wrap_client_create(wrapped, instance, args, kwargs):
            # Existing code for handling normal message creation
            
            # Add detection of tool usage
            result = original_create(*args, **kwargs)
            
            # Check if tool calls were made
            if hasattr(result, 'tool_calls') and result.tool_calls:
                for tool_call in result.tool_calls:
                    self._layer.append_action(
                        session_id=session_id,
                        kind=SessionActionKind.TOOLS,
                        start_time=start_time,
                        end_time=datetime.now(timezone.utc),
                        attributes={
                            "source": "anthropic",
                            "model.id": kwargs.get("model"),
                            "tool.name": tool_call.name,
                        },
                        data={
                            "tool_input": tool_call.input,
                            "tool_output": tool_call.output if hasattr(tool_call, 'output') else None
                        },
                        scanners=[
                            SessionActionScanner(
                                name="usage",
                                data={
                                    "input_tokens": getattr(result.usage, "input_tokens", 0),
                                    "output_tokens": getattr(result.usage, "output_tokens", 0),
                                    "total_tokens": getattr(result.usage, "total_tokens", 0),
                                },
                            )
                        ] if hasattr(result, 'usage') else None
                    )
            
            return result
        
    def _instrument_tool_results(self):
        """Instrument tool results sent back to Anthropic."""
        
        @wrapt.patch_function_wrapper('anthropic', 'Client', 'messages.create')
        def wrap_tool_results(wrapped, instance, args, kwargs):
            # Check if this is a tool result message
            tool_results = None
            for content in kwargs.get('messages', []):
                if isinstance(content, dict) and content.get('type') == 'tool_result':
                    tool_results = content
                    break
            
            if tool_results:
                # Log the tool result
                self._layer.append_action(
                    session_id=self._extract_session_id(kwargs),
                    kind=SessionActionKind.TOOLS,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    attributes={
                        "source": "anthropic",
                        "model.id": kwargs.get("model"),
                        "tool.result": True,
                        "tool_use_id": tool_results.get('tool_use_id')
                    },
                    data={
                        "content": tool_results.get('content')
                    }
                )
            
            return wrapped(*args, **kwargs)