# Простые состояния для FSM (можно расширять)
class AskFlow:
    waiting_for_topic = "waiting_for_topic"
    waiting_for_question = "waiting_for_question"
    confirming = "confirming"

# Хранилище состояний (в памяти, для демо)
_state_storage = {}

def get_state(user_id: str) -> str | None:
    return _state_storage.get(user_id)

def set_state(user_id: str, state: str) -> None:
    _state_storage[user_id] = state

def clear_state(user_id: str) -> None:
    _state_storage.pop(user_id, None)