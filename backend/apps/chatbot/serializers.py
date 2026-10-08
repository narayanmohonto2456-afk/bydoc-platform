from rest_framework import serializers


class ChatTurnSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("user", "assistant"))
    content = serializers.CharField(max_length=600, trim_whitespace=True)


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=600, trim_whitespace=True)
    history = ChatTurnSerializer(many=True, required=False)

    def validate_history(self, value):
        if len(value) > 6:
            raise serializers.ValidationError("Keep at most six previous messages.")
        return value


class ChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    topic = serializers.CharField()


class ChatStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    ai_enabled = serializers.BooleanField()
