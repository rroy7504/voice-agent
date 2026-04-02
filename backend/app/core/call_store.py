from app.models.call import CallState


class CallStore:
    def __init__(self):
        self._calls: dict[str, CallState] = {}

    def create_call(self, call_id: str) -> CallState:
        call = CallState(call_id=call_id)
        self._calls[call_id] = call
        return call

    def get_call(self, call_id: str) -> CallState | None:
        return self._calls.get(call_id)

    def update_call(self, call_id: str, **kwargs) -> CallState | None:
        call = self._calls.get(call_id)
        if call is None:
            return None
        for key, value in kwargs.items():
            setattr(call, key, value)
        return call

    def list_calls(self) -> list[CallState]:
        return list(self._calls.values())


call_store = CallStore()
