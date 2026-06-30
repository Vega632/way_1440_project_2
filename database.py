import os
from dotenv import load_dotenv
from datetime import date

load_dotenv()

# Заглушка-хранилище в памяти (работает всегда!)
memory_db = {
    "users": {},
    "challenges": {},
    "daily_logs": [],
    "goals": [],
    "achievements": []
}
challenge_id_counter = 1

class Database:
    @staticmethod
    def init_user(user_id, username, first_name):
        if user_id not in memory_db["users"]:
            memory_db["users"][user_id] = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name
            }
            print(f"User {first_name} created")
    
    @staticmethod
    def get_user(user_id):
        return memory_db["users"].get(user_id)
    
    @staticmethod
    def create_challenge(user_id, exercise_type, daily_target, days=None):
        global challenge_id_counter
        total_target = daily_target * days if days else None
        
        challenge = {
            "id": challenge_id_counter,
            "user_id": user_id,
            "exercise_type": exercise_type,
            "daily_target": daily_target,
            "total_target": total_target,
            "days": days,
            "current_streak": 0,
            "best_streak": 0,
            "total_done": 0,
            "is_active": True
        }
        memory_db["challenges"][challenge_id_counter] = challenge
        challenge_id_counter += 1
        return challenge
    
    @staticmethod
    def get_active_challenge(user_id):
        for ch in memory_db["challenges"].values():
            if ch["user_id"] == user_id and ch["is_active"]:
                return ch
        return None
    
    @staticmethod
    def add_progress(user_id, challenge_id, amount):
        challenge = memory_db["challenges"].get(challenge_id)
        if not challenge:
            return 0
        
        memory_db["daily_logs"].append({
            "user_id": user_id,
            "challenge_id": challenge_id,
            "amount": amount,
            "log_date": str(date.today())
        })
        
        today = str(date.today())
        daily_total = sum(log['amount'] for log in memory_db["daily_logs"] 
                         if log["user_id"] == user_id and log["challenge_id"] == challenge_id and log["log_date"] == today)
        
        challenge["total_done"] += amount
        
        if daily_total >= challenge["daily_target"]:
            challenge["current_streak"] += 1
        if challenge["current_streak"] > challenge["best_streak"]:
            challenge["best_streak"] = challenge["current_streak"]
        
        return challenge["daily_target"] - daily_total
    
    @staticmethod
    def get_stats(user_id):
        return [ch for ch in memory_db["challenges"].values() if ch["user_id"] == user_id and ch["is_active"]]
    
    @staticmethod
    def add_goal(user_id, goal_text, month_year):
        memory_db["goals"].append({
            "user_id": user_id,
            "goal_text": goal_text,
            "month_year": month_year
        })
    
    @staticmethod
    def check_achievement(user_id, challenge):
        achievements = []
        streak = challenge.get('current_streak', 0)
        total = challenge.get('total_done', 0)
        
        existing_names = [a.get('achievement_name') for a in memory_db["achievements"] if a["user_id"] == user_id]
        
        if streak in [7, 14, 30]:
            ach_name = f"Стрик {streak} дней"
            if ach_name not in existing_names:
                memory_db["achievements"].append({
                    "user_id": user_id,
                    "achievement_name": ach_name,
                    "achievement_type": "streak",
                    "unlocked_at": str(date.today())
                })
                achievements.append(ach_name)
        
        if total in [1000, 3000, 10000]:
            ach_name = f"{total} повторений"
            if ach_name not in existing_names:
                memory_db["achievements"].append({
                    "user_id": user_id,
                    "achievement_name": ach_name,
                    "achievement_type": "reps",
                    "unlocked_at": str(date.today())
                })
                achievements.append(ach_name)
        
        return achievements