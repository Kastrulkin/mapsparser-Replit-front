import json

from services.operator_conversations import finish_operator_action, reject_operator_action


class RecordingCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((" ".join(query.split()).lower(), params or ()))


def test_finish_operator_action_updates_the_chat_message_state():
    cursor = RecordingCursor()
    result = {"status": "completed", "chat_response": "Изменение применено."}

    finish_operator_action(cursor, action_id="action-1", result=result)

    assert len(cursor.calls) == 2
    message_query, message_params = cursor.calls[1]
    assert "update operatormessages" in message_query
    assert "status = 'completed'" in message_query
    assert message_params[0] == "Изменение применено."
    assert json.loads(message_params[1])["status"] == "completed"
    assert message_params[2:] == ("action-1", "action-1")


def test_reject_operator_action_updates_the_chat_message_state():
    cursor = RecordingCursor()
    result = {"status": "rejected", "chat_response": "Действие отклонено."}

    reject_operator_action(cursor, action_id="action-2", result=result)

    assert len(cursor.calls) == 2
    message_query, message_params = cursor.calls[1]
    assert "update operatormessages" in message_query
    assert "status = 'rejected'" in message_query
    assert message_params[0] == "Действие отклонено."
    assert json.loads(message_params[1])["status"] == "rejected"
    assert message_params[2:] == ("action-2", "action-2")
