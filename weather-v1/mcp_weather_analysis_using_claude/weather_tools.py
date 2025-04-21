from layer_sdk_integration.layer_sdk.schemas import SessionActionKind
from datetime import datetime, timezone
import json


def log_as_tool(layer_client):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract session_id but don't pass it to func
            session_id = kwargs.pop('session_id', None)
            
            start_time = datetime.now(timezone.utc)
            result = await func(*args, **kwargs)
            end_time = datetime.now(timezone.utc)
            
            if session_id:
                try:
                    layer_client.append_action(
                        session_id=session_id,
                        kind="completion_output",
                        start_time=start_time,
                        end_time=end_time,
                        attributes={
                            "model.id": "claude-3-sonnet",
                            "tool.name": func.__name__
                        },
                        data={"messages": [{"content": str(result)[:1000], "role": "assistant"}]}
                    )
                except Exception as e:
                    print(f"Error: {e}")
            
            return result
        return wrapper
    return decorator