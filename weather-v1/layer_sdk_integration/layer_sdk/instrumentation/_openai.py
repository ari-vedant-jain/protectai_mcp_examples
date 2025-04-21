from typing import List, Optional
from datetime import datetime, timezone
from dataclasses import asdict

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


class OpenAIInstrumentation(BaseInstrumentor):
    """Instrumentation class for OpenAI SDK."""

    def supports(self) -> bool:
        """Check if the OpenAI SDK is supported."""
        version_correct = is_module_version_more_than("openai", "1.18.0")

        if version_correct is None:
            return False

        return version_correct

    def instrument(self):
        """Instrument the OpenAI SDK."""
        self._instrument_chat_completion()
        self._instrument_embedding()
        self._instrument_moderation()

    def _extract_session_id(self, kwargs: dict) -> Optional[str]:
        headers = kwargs.get("extra_headers", {})

        if "Layer-Session-Id" in headers:
            return headers.get("Layer-Session-Id")

        return headers.get("X-Layer-Session-Id")

    def _create_or_append(
            self,
            session_id: Optional[str],
            actions: List[SessionActionRequest],
    ) -> str:
        if session_id:
            for action in actions:
                self._layer.append_action(
                    session_id,
                    **asdict(action),
                )

                logger.debug(f"Appended {action.kind.value} action to '{session_id}' session")

            return session_id

        logger.debug(f"No session id was provided. "
                     f"Creating a new session with {len(actions)} actions")

        new_session_id = self._layer.create_session(
            attributes={
                "source": "instrumentation.openai",
                "openai.version": get_module_version("openai")
            },
            actions=actions,
        )

        return new_session_id

    def _process_completion_stream(self, session_id, start_time, result):
        completion_content = ""
        completion_role = ""
        completion_model = ""
        chunk_count = 0
        for chunk in result:
            if len(chunk.choices) > 0:
                if not hasattr(chunk.choices[0], "delta"):
                    continue

                if hasattr(chunk.choices[0].delta, "content"):
                    content = chunk.choices[0].delta.content
                    if content:
                        completion_content += content

                if hasattr(chunk.choices[0].delta, "role"):
                    role = chunk.choices[0].delta.role
                    if role:
                        completion_role = role

                completion_model = chunk.model
                chunk_count += 1

                yield chunk

        self._create_or_append(session_id, [
            SessionActionRequest(
                kind=SessionActionKind.COMPLETION_OUTPUT,
                start_time=start_time,
                end_time=datetime.now(timezone.utc),
                attributes={
                    "stream": "true",
                    "model.id": completion_model,
                    "chunk.count": chunk_count,
                },
                data={
                    "messages": [
                        {
                            "content": completion_content,
                            "role": completion_role,
                        }
                    ],
                },
            )
        ])

    def _instrument_chat_completion(self):
        @wrapt.patch_function_wrapper('openai.resources.chat.completions', 'Completions.create')
        def wrapper(wrapped, instance, args, kwargs):
            messages = [
                {
                    "role": message.get("role"),
                    "content": message.get("content"),
                    "user": message.get("user", ""),
                }
                for message in kwargs.get("messages")
            ]

            attrs = {
                "model.id": kwargs.get("model"),
                "model.stream": "true" if kwargs.get("stream", False) else "false",
            }

            attr_has_keys = [
                "response_format",
                "metadata",
                "tools",
            ]
            for key in attr_has_keys:
                attrs[f"model.has_{key}"] = "false" if kwargs.get(key, None) else "true"

            attr_keys = [
                "max_tokens",
                "temperature",
                "frequency_penalty",
                "max_completion_tokens",
                "logit_bias",
                "logprobs",
                "modalities",
                "n",
                "presence_penalty",
                "stop",
                "seed",
                "top_p",
                "user",
            ]
            for key in attr_keys:
                if key in kwargs and kwargs[key] is not None:
                    attrs[f"model.{key}"] = kwargs[key]

            session_id = self._create_or_append(self._extract_session_id(kwargs), [
                SessionActionRequest(
                    kind=SessionActionKind.COMPLETION_PROMPT,
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    attributes=attrs,
                    data={
                        "messages": messages,
                    },
                )
            ])

            result = None
            exception_to_raise = None
            start_time = datetime.now(timezone.utc)
            try:
                result = wrapped(*args, **kwargs)
            except Exception as e:
                exception_to_raise = e

            if exception_to_raise or result is None:
                self._create_or_append(session_id, [
                    SessionActionRequest(
                        kind=SessionActionKind.COMPLETION_OUTPUT,
                        start_time=start_time,
                        end_time=datetime.now(timezone.utc),
                        error=SessionActionError(message=str(exception_to_raise))
                    )
                ])

                raise exception_to_raise

            is_stream = kwargs.get("stream", False)
            if is_stream:
                return self._process_completion_stream(session_id, start_time, result)

            completions_scanners = None
            completions_messages = []

            if result.usage is not None:
                completions_scanners = [
                    SessionActionScanner(
                        name="usage",
                        data={
                            "prompt_tokens": result.usage.prompt_tokens,
                            "completion_tokens": result.usage.completion_tokens,
                            "total_tokens": result.usage.total_tokens,
                        },
                    )
                ]

            for choice in result.choices:
                if choice.message.content is None:
                    continue

                completions_messages.append({
                    "content": choice.message.content,
                    "role": choice.message.role,
                })

            self._create_or_append(session_id, [
                SessionActionRequest(
                    kind=SessionActionKind.COMPLETION_OUTPUT,
                    start_time=start_time,
                    end_time=datetime.now(timezone.utc),
                    attributes={
                        "model.created": result.created,
                        "model.id": result.model,
                        "model.completion_id": result.id,
                    },
                    data={
                        "messages": completions_messages,
                    },
                    scanners=completions_scanners,
                )
            ])

            return result

    def _instrument_embedding(self):
        @wrapt.patch_function_wrapper('openai.resources.embeddings', 'Embeddings.create')
        def wrapped_embedding_create(wrapped, instance, args, kwargs):
            error = None
            exception_to_raise = None
            result = None

            start_time = datetime.now(timezone.utc)
            try:
                result = wrapped(*args, **kwargs)  # type: ignore
            except Exception as e:
                exception_to_raise = e
                error = SessionActionError(message=str(e))
            finally:
                end_time = datetime.now(timezone.utc)

            scanners = None
            if error is None:
                scanners = [
                    SessionActionScanner(
                        name="usage",
                        data={
                            "prompt_tokens": result.usage.prompt_tokens,  # type: ignore[reportOptionalMemberAccess]
                            "total_tokens": result.usage.total_tokens,  # type: ignore[reportOptionalMemberAccess]
                        },
                    )
                ]

            embedding_input = kwargs.get("input")
            if isinstance(embedding_input, str):
                embedding_input = [embedding_input]

            attributes = {
                "model.id": kwargs.get("model", "text-embedding-ada-002"),
                "model.encoding_format": kwargs.get("encoding_format", "float"),
            }

            if "user" in kwargs:
                attributes["model.user"] = kwargs.get("user")

            action = SessionActionRequest(
                kind=SessionActionKind.EMBEDDINGS,
                start_time=start_time,
                end_time=end_time,
                attributes=attributes,
                data={
                    "input": embedding_input,
                },
                scanners=scanners,
                error=error
            )

            self._create_or_append(self._extract_session_id(kwargs), [action])

            if exception_to_raise:
                raise exception_to_raise

            return result

    def _instrument_moderation(self):
        @wrapt.patch_function_wrapper('openai.resources.moderations', 'Moderations.create')
        def wrapped_moderation_create(wrapped, instance, args, kwargs):
            error = None
            exception_to_raise = None
            result = None

            start_time = datetime.now(timezone.utc)
            try:
                result = wrapped(*args, **kwargs)
            except Exception as e:
                exception_to_raise = e
                error = SessionActionError(message=str(e))
            finally:
                end_time = datetime.now(timezone.utc)

            scanners = None
            if error is None and len(result.results) > 0:  # type: ignore[reportOptionalMemberAccess]
                scanners = []
                for index, item in enumerate(result.results):  # type: ignore[reportOptionalMemberAccess]
                    scanners.append(SessionActionScanner(
                        name=f"openai_moderation_{index}",
                        data=item.categories.to_dict(),
                    ))

            moderation_input = kwargs.get("input")
            if isinstance(moderation_input, str):
                moderation_input = [moderation_input]

            action = SessionActionRequest(
                kind=SessionActionKind.MODERATION,
                start_time=start_time,
                end_time=end_time,
                attributes={
                    "model.id": kwargs.get("model", "text-moderation-latest"),
                },
                data={
                    "input": moderation_input,
                },
                scanners=scanners,
                error=error
            )

            self._create_or_append(self._extract_session_id(kwargs), [action])

            if exception_to_raise:
                raise exception_to_raise

            return result
