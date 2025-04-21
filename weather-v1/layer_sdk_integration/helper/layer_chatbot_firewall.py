import time
import anthropic
import logging
from datetime import datetime, timezone
from layer_sdk import layer, SessionActionKind, FirewallLookupDecision
from layer_sdk.exceptions import LayerFirewallSessionBlocked, LayerFirewallHTTPError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("claude-firewall")

def initialize_session(session_id=None, model_id=None):
    """
    Initialize session and validate model_id.
    
    Args:
        session_id (str, optional): The Layer session ID to use. If None, a new session will be created.
        model_id (str, optional): The Claude model ID to use. If None, default model will be used.
        
    Returns:
        tuple: (session_id, model_id) - The session ID and model ID to use
    """
    # Ensure we have a model ID
    if model_id is None:
        import os
        model_id = os.environ.get("CLAUDE_MODEL_ID", "claude-3-7-sonnet-20250219")
        
    # Make sure model_id is actually set to a string value
    if not model_id or not isinstance(model_id, str):
        model_id = "claude-3-7-sonnet-20250219"  # Fallback to a default model
    
    # Create a new session if none was provided
    if session_id is None:
        try:
            logger.info("Creating new Layer session")
            session_id = layer.create_session(
                attributes={
                    "source": "claude-firewall-demo",
                    "model.id": model_id
                }
            )
            logger.info(f"Created new session: {session_id}")
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            raise
            
    return session_id, model_id


def check_firewall(session_id):
    """
    Check the firewall status for the given session.
    
    Args:
        session_id (str): The Layer session ID to check
        
    Returns:
        str: The firewall decision: "block", "alert", or "pass"
    """
    try:
        logger.info(f"Checking firewall for session {session_id}")
        firewall_response = layer.firewall_session_lookup(session_id)
        
        logger.info(f"Firewall decision: {firewall_response.decision}")
        
        # Convert to string for consistent comparison
        firewall_decision_str = str(firewall_response.decision).lower()
        
        if firewall_decision_str == "block" or firewall_response.decision == FirewallLookupDecision.BLOCK:
            return "block"
        elif firewall_decision_str == "alert" or firewall_response.decision == FirewallLookupDecision.ALERT:
            return "alert"
        else:
            return "pass"
            
    except Exception as e:
        logger.error(f"Firewall check error: {str(e)}")
        # Default to "pass" on error (you could change this to be more conservative)
        return "pass"


def get_claude_response(prompt, session_id, model_id):
    """
    Call Claude API and get the response.
    
    Args:
        prompt (str): The user's prompt to send to Claude
        model_id (str): The Claude model ID to use
        
    Returns:
        tuple: (response_content, chunk_count) - The response from Claude and chunk count,
               or (error_message, 0) if there was an error
    """
    try:
        logger.info("Starting Anthropic API streaming call")
        client = anthropic.Client()
        
        headers = {
            "X-Layer-Session-Id": session_id,
            "Layer-User-Id": "ari-claude-009",
            "Layer-Source": "ari-claude-demo",
        }
        
        # Variables to collect response
        response_content = ""
        chunk_count = 0
        
        try:
            stream = client.messages.create(
                model=model_id,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                stream=True,
                extra_headers=headers  
            )
            
            for event in stream:
                if hasattr(event, 'type'):
                    if event.type == "content_block_delta":
                        text = event.delta.text
                        if text:
                            response_content += text
                            chunk_count += 1
                    elif event.type == "error":
                        # Handle error events in the stream
                        logger.error(f"Error in stream: {event}")
                        return "Sorry, I can't respond to this request due to a streaming error.", 0
        except Exception as streaming_error:
            logger.error(f"Error during streaming: {streaming_error}")
            return "Sorry, I can't respond to this request due to a streaming error.", 0
            
        # Handle empty responses
        if response_content == "":
            logger.error("Empty response from Anthropic API")
            return "Sorry, I can't respond to this request due to an empty response.", 0
            
        return response_content, chunk_count
        
    except Exception as e:
        logger.error(f"Error in API call setup: {str(e)}")
        return "Sorry, I can't respond to this request due to an error.", 0


def log_to_layer(session_id, kind, model_id, attributes=None, data=None):
    """
    Log an action to Layer.
    
    Args:
        session_id (str): The Layer session ID to use
        kind (SessionActionKind): The kind of action (COMPLETION_PROMPT or COMPLETION_OUTPUT)
        model_id (str): The Claude model ID used
        attributes (dict, optional): Additional attributes to log
        data (dict, optional): The data to log
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize default attributes and data
        if attributes is None:
            attributes = {}
        if data is None:
            data = {}
            
        # Add required attributes
        required_attributes = {
            "model.id": model_id,
            "source": "claude-firewall-demo"
        }
        # Merge with user-provided attributes (user-provided take precedence)
        attributes = {**required_attributes, **attributes}
        
        # Log the action
        logger.info(f"Logging {kind.value} action for session {session_id}")
        layer.append_action(
            session_id,
            kind=kind,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            attributes=attributes,
            data=data
        )
        return True
        
    except Exception as e:
        logger.error(f"Error logging action: {str(e)}")
        return False


def call_claude_with_firewall(prompt, session_id=None, model_id=None):
    """
    Main function that calls Claude with firewall protection.
    
    Args:
        prompt (str): The user's prompt to send to Claude
        session_id (str, optional): The Layer session ID to use. If None, a new session will be created.
        model_id (str, optional): The Claude model ID to use. If None, default model will be used.
        
    Returns:
        tuple: (response_content, session_id) - The response from Claude and the session ID used.
    """
    # 1. Initialize session and model ID
    session_id, model_id = initialize_session(session_id, model_id)
    
    # 2. Check firewall
    firewall_decision = check_firewall(session_id)
    
    # Log prompt action - Don't need this when `enable_firewall_instrumentation=True``
    # log_to_layer(
    #     session_id,
    #     SessionActionKind.COMPLETION_PROMPT,
    #     model_id,
    #     attributes={"firewall.decision": firewall_decision},
    #     data={"messages": [{"role": "user", "content": prompt}]}
    # )
    
    if firewall_decision == "block":
        # Return blocked response: Need this even when `enable_firewall_instrumentation=True``
        response = "Sorry, I can't respond to this request."
        # Log the blocked response
        log_to_layer(
            session_id,
            SessionActionKind.COMPLETION_OUTPUT,
            model_id,
            attributes={"firewall.decision": firewall_decision},
            data={"messages": [{"role": "assistant", "content": response}]}
        )
        return response, session_id
    
    # 3. Call Claude API
    response, chunk_count = get_claude_response(prompt, session_id, model_id)
    
    # 4. Check firewall again after response
    firewall_decision = check_firewall(session_id)
    
    # 5. Log the response
    # log_to_layer(
    #     session_id,
    #     SessionActionKind.COMPLETION_OUTPUT,
    #     model_id,
    #     attributes={"firewall.decision": firewall_decision},
    #     data={"messages": [{"role": "assistant", "content": response}]}
    # )
    
    # 6. Handle post-response firewall block
    if firewall_decision == "block":
        return "Sorry, I can't respond to this request.", session_id
    
    return response, session_id