class DeepSeekAgent:
    @staticmethod
    def get_motivation(context):
        try:
            from openai import OpenAI
            import os
            client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Ты — жесткий цифровой коуч «Путь-24». Девиз: «Ты либо строишь себя, либо смотришь, как другие строят». Добавь 1-2 предложения живости. Будь дерзким. Отвечай на русском."},
                    {"role": "user", "content": context}
                ],
                max_tokens=150,
                temperature=0.8
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"DeepSeek error: {e}")
            return "Продолжай в том же духе, воин. Дисциплина — это свобода. 💪"
    
    @staticmethod
    def answer_question(question, user_data):
        try:
            from openai import OpenAI
            import os
            client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"Ты — цифровой коуч «Путь-24». Данные пользователя: {user_data}"},
                    {"role": "user", "content": question}
                ],
                max_tokens=300,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"DeepSeek error: {e}")
            return "Я верю в твою дисциплину. Продолжай движение. 🔥"