import telebot
from telebot import types
import time
import json
import os
import random
from datetime import datetime
import threading

TOKEN = "7373819384:AAFlIfLd2s9pBd_2qb5d2bFDxPo8tmanoeg"
ADMIN_ID = 8221522366

print("🎮 در حال راه‌اندازی ربات مافیا...")

# ========== دیتابیس ساده ==========
class SimpleDB:
    def __init__(self):
        self.files = ['users.json', 'games.json']
        for f in self.files:
            if not os.path.exists(f):
                with open(f, 'w', encoding='utf-8') as file:
                    json.dump({}, file)
    
    def load(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save(self, filename, data):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

db = SimpleDB()
bot = telebot.TeleBot(TOKEN)

# ========== ذخیره بازی‌های فعال ==========
active_games = {}
game_sessions = {}

# ========== کلاس بازی ==========
class GameSession:
    def __init__(self, game_id, creator_id, scenario):
        self.id = game_id
        self.creator_id = creator_id
        self.scenario = scenario
        self.players = []
        self.status = "waiting"  # waiting, roles, night, day, voting, ended
        self.phase = "setup"
        self.day = 0
        self.night = 0
        
        # نقش‌ها بر اساس سناریو
        self.roles = self.get_scenario_roles()
        self.assigned_roles = {}
        self.alive_players = []
        self.dead_players = []
        
    def get_scenario_roles(self):
        """نقش‌های هر سناریو"""
        scenarios = {
            "ساده": ["شهروند", "شهروند", "شهروند", "شهروند", "شهروند", "مافیا", "مافیا", "مافیا", "دکتر"],
            "پیشرفته": ["شهروند", "شهروند", "شهروند", "شهروند", "شهروند", "دکتر", "کارآگاه", 
                       "مافیا", "مافیا", "مافیا", "آدم‌گرگ"],
            "سخت": ["شهروند", "شهروند", "شهروند", "دکتر", "کارآگاه", "تیرانداز",
                   "مافیا", "مافیا", "مافیا", "گادفادر", "آدم‌گرگ", "دیوانه"],
            "ویژه": ["شهروند", "دکتر", "کارآگاه", "تیرانداز", "محافظ", "قاضی", "روانشناس",
                    "گادفادر", "جادوگر", "فریبکار", "آدم‌گرگ", "خبرچین"]
        }
        return scenarios.get(self.scenario, scenarios["ساده"])
    
    def add_player(self, user_id, username):
        """اضافه کردن بازیکن"""
        if len(self.players) < len(self.roles):
            player = {
                "id": user_id,
                "name": username,
                "ready": False,
                "role": None,
                "alive": True,
                "votes": 0
            }
            self.players.append(player)
            return True
        return False
    
    def assign_roles(self):
        """توزیع نقش‌ها"""
        if len(self.players) != len(self.roles):
            return False
        
        random.shuffle(self.players)
        random.shuffle(self.roles)
        
        for i, player in enumerate(self.players):
            player["role"] = self.roles[i]
            self.assigned_roles[player["id"]] = self.roles[i]
            
            # ارسال نقش به هر بازیکن
            try:
                role_desc = self.get_role_description(self.roles[i])
                bot.send_message(
                    player["id"],
                    f"🎭 **نقش شما مشخص شد!**\n\n"
                    f"👤 شما: {player['name']}\n"
                    f"🎯 نقش: **{self.roles[i]}**\n"
                    f"📋 {role_desc}\n\n"
                    f"🎮 بازی بزودی شروع می‌شود..."
                )
            except:
                pass
        
        self.status = "roles_assigned"
        self.alive_players = self.players.copy()
        return True
    
    def get_role_description(self, role):
        """توضیح نقش"""
        descriptions = {
            "شهروند": "شهروند معمولی - بدون قدرت ویژه",
            "دکتر": "هر شب می‌تواند یک نفر را درمان کند",
            "کارآگاه": "هر شب وفاداری یک نفر را می‌فهمد",
            "تیرانداز": "یک بار می‌تواند شبانه شلیک کند",
            "محافظ": "هر شب از یک نفر محافظت می‌کند",
            "قاضی": "رای او دو برابر حساب می‌شود",
            "روانشناس": "می‌تواند یک نفر را سایلنت کند",
            "خبرچین": "پیام‌های خصوصی را می‌بیند",
            "مافیا": "هر شب با هم‌تیمی‌ها یک نفر را می‌کشد",
            "گادفادر": "رهبر مافیا - مصون از شناسایی",
            "جادوگر": "قدرت‌های دیگران را خنثی می‌کند",
            "فریبکار": "می‌تواند خود را شهروند نشان دهد",
            "آدم‌گرگ": "هر شب یک نفر را می‌کشد - برنده انفرادی",
            "دیوانه": "باید اعدام شود تا برنده شود"
        }
        return descriptions.get(role, "نقش ویژه")
    
    def start_night(self):
        """شروع شب"""
        self.status = "night"
        self.night += 1
        
        # ارسال پیام به همه بازیکنان
        for player in self.alive_players:
            try:
                bot.send_message(
                    player["id"],
                    f"🌙 **شب {self.night}**\n\n"
                    f"🔒 همه چشم‌ها بسته...\n"
                    f"⏳ منتظر اقدامات..."
                )
            except:
                pass
        
        return True
    
    def process_night(self):
        """پردازش شب"""
        # اینجا در بازی واقعی، اقدامات بازیکنان پردازش می‌شود
        # برای سادگی، یک کشته تصادفی انتخاب می‌کنیم
        if self.alive_players:
            # مافیا یک نفر را می‌کشد
            mafia_players = [p for p in self.alive_players if p["role"] in ["مافیا", "گادفادر", "جادوگر", "فریبکار"]]
            if mafia_players:
                targets = [p for p in self.alive_players if p["role"] not in ["مافیا", "گادفادر", "جادوگر", "فریبکار"]]
                if targets:
                    victim = random.choice(targets)
                    victim["alive"] = False
                    self.dead_players.append(victim)
                    self.alive_players.remove(victim)
                    
                    # شانس درمان توسط دکتر
                    doctor = next((p for p in self.alive_players if p["role"] == "دکتر"), None)
                    if doctor and random.random() < 0.5:  # 50% شانس درمان
                        victim["alive"] = True
                        self.alive_players.append(victim)
                        self.dead_players.remove(victim)
                        return None
                    
                    return victim
        
        return None
    
    def start_day(self, night_victim=None):
        """شروع روز"""
        self.status = "day"
        self.day += 1
        
        day_text = f"☀️ **صبح روز {self.day}**\n\n"
        
        if night_victim:
            day_text += f"💀 **کشته‌شده شب:**\n"
            day_text += f"• {night_victim['name']} ({night_victim['role']})\n\n"
        else:
            day_text += "🎉 **هیچکس در شب کشته نشد!**\n\n"
        
        day_text += f"👥 **بازیکنان زنده ({len(self.alive_players)} نفر):**\n"
        for i, player in enumerate(self.alive_players, 1):
            day_text += f"{i}. {player['name']} (؟)\n"
        
        day_text += "\n💬 **زمان بحث و تبادل نظر**\n"
        day_text += "⏰ ۲ دقیقه فرصت دارید..."
        
        # ارسال به همه بازیکنان زنده
        for player in self.alive_players:
            try:
                bot.send_message(player["id"], day_text)
            except:
                pass
        
        return day_text

# ========== منوها ==========
def create_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.row("🎮 بازی جدید", "📊 جدول", "👤 پروفایل")
    markup.row("📖 سناریوها", "⚙️ تنظیمات", "🆘 راهنما")
    return markup

def create_game_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 ساده (۹ نفر)", callback_data="create_simple"),
        types.InlineKeyboardButton("⭐ پیشرفته (۱۱ نفر)", callback_data="create_advanced"),
        types.InlineKeyboardButton("🔥 سخت (۱۲ نفر)", callback_data="create_hard"),
        types.InlineKeyboardButton("👑 ویژه (۱۲ نفر)", callback_data="create_special"),
        types.InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")
    )
    return markup

# ========== دستورات اصلی ==========
@bot.message_handler(commands=['start', 'restart'])
def start_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "کاربر"
    
    users = db.load("users.json")
    uid = str(user_id)
    
    if uid not in users:
        users[uid] = {
            "name": first_name,
            "score": 0,
            "coins": 1000,
            "games": 0,
            "wins": 0,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        db.save("users.json", users)
    
    welcome_text = f"""
🎮 **ذهات بازی مافیا**  
✅ سیستم: فعال | VPN: توصیه می‌شود

👤 {first_name}
🎯 امتیاز: {users[uid]['score']}
💰 سکه: {users[uid]['coins']:,}

🕐 {datetime.now().strftime("%H:%M")}

👇 **منوی اصلی:**
"""
    
    bot.send_message(user_id, welcome_text, reply_markup=create_main_menu())
    print(f"👤 کاربر {user_id} وارد شد")

@bot.message_handler(func=lambda m: m.text == "🎮 بازی جدید")
def new_game_command(message):
    user_id = message.from_user.id
    
    game_text = """
🎮 **ایجاد بازی جدید**

👇 **انتخاب سناریو:**

🎯 **ساده** (۹ نفره)
• ترکیب استاندارد
• بهترین برای شروع

⭐ **پیشرفته** (۱۱ نفره)
• نقش‌های ویژه فعال
• بازی متعادل

🔥 **سخت** (۱۲ نفره)
• چالش برانگیز
• برای بازیکنان با تجربه

👑 **ویژه** (۱۲ نفره)
• ۱ شهروند ساده
• ۱۱ نقش ویژه

👇 **یک گزینه انتخاب کنید:**
"""
    
    bot.send_message(user_id, game_text, reply_markup=create_game_menu())

@bot.message_handler(func=lambda m: m.text == "📖 سناریوها")
def scenarios_command(message):
    user_id = message.from_user.id
    
    scenarios_text = """
🎭 **لیست کامل سناریوها**

🟢 **همیشه باز و فعال:**

1️⃣ **ساده** (۹ نفره)
   • ۶ شهروند + ۳ مافیا
   • سریع و ساده
   • مدت: ۱۵-۲۰ دقیقه

2️⃣ **پیشرفته** (۱۱ نفره)
   • ۷ شهروند + ۳ مافیا + ۱ آدم‌گرگ
   • نقش دکتر و کارآگاه فعال
   • مدت: ۲۰-۳۰ دقیقه

3️⃣ **سخت** (۱۲ نفره)
   • ۵ شهروند + ۴ مافیا + ۳ مستقل
   • نقش‌های: گادفادر، دیوانه
   • مدت: ۲۵-۳۵ دقیقه

4️⃣ **ویژه** (۱۲ نفره)
   • ۱ شهروند ساده + ۱۱ نقش ویژه
   • چالش استراتژیک بالا
   • مدت: ۳۰-۴۰ دقیقه

🎮 **همه سناریوها برای همه بازیکنان قابل دسترسی است!**
"""
    
    bot.send_message(user_id, scenarios_text)

@bot.message_handler(func=lambda m: m.text == "📊 جدول")
def leaderboard_command(message):
    user_id = message.from_user.id
    users = db.load("users.json")
    
    # مرتب‌سازی
    top_players = sorted(
        [(uid, data) for uid, data in users.items()],
        key=lambda x: x[1].get("score", 0),
        reverse=True
    )[:10]
    
    text = "🏆 **۱۰ بازیکن برتر**\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (uid, player) in enumerate(top_players):
        if i < len(medals):
            text += f"{medals[i]} **{player.get('name', 'کاربر')}**\n"
            text += f"   امتیاز: {player.get('score', 0):,}\n"
            text += f"   بازی‌ها: {player.get('games', 0)}\n\n"
    
    bot.send_message(user_id, text)

@bot.message_handler(func=lambda m: m.text == "👤 پروفایل")
def profile_command(message):
    user_id = message.from_user.id
    users = db.load("users.json")
    user = users.get(str(user_id), {})
    
    win_rate = (user.get("wins", 0) / user.get("games", 1) * 100) if user.get("games", 0) > 0 else 0
    
    text = f"""
👤 **پروفایل**

📛 نام: {user.get('name', 'کاربر')}
🎯 امتیاز: {user.get('score', 0):,}
💰 سکه: {user.get('coins', 0):,}

🎮 **آمار بازی:**
• کل بازی‌ها: {user.get('games', 0)}
• بردها: {user.get('wins', 0)}
• درصد برد: {win_rate:.1f}%

📅 عضویت: {user.get('created', 'نامشخص')}
"""
    
    bot.send_message(user_id, text)

# ========== سیستم بازی ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith("create_"))
def create_game_callback(call):
    user_id = call.from_user.id
    scenario_type = call.data.split("_")[1]
    
    scenario_names = {
        "simple": "ساده",
        "advanced": "پیشرفته", 
        "hard": "سخت",
        "special": "ویژه"
    }
    
    scenario_name = scenario_names.get(scenario_type, "ساده")
    
    # ایجاد بازی جدید
    game_id = f"game_{user_id}_{int(time.time())}"
    game = GameSession(game_id, user_id, scenario_name)
    game_sessions[game_id] = game
    active_games[game_id] = game
    
    # اضافه کردن سازنده
    user = call.from_user
    game.add_player(user_id, user.first_name)
    
    game_info = f"""
🎮 **بازی {scenario_name} ایجاد شد!**

🏷️ کد بازی: `{game_id[-6:]}`
👤 میزبان: {user.first_name}
👥 بازیکنان: ۱/{len(game.roles)}
🎯 سناریو: {scenario_name}

📋 **برای عضویت دوستان کد زیر را بفرستید:**
`{game_id[-6:]}`

👇 **گزینه‌های مدیریت:**
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👥 اضافه کردن بازیکن", callback_data=f"add_player:{game_id}"),
        types.InlineKeyboardButton("🎭 توزیع نقش‌ها", callback_data=f"assign_roles:{game_id}"),
        types.InlineKeyboardButton("🚀 شروع بازی", callback_data=f"start_game:{game_id}"),
        types.InlineKeyboardButton("❌ حذف بازی", callback_data=f"delete_game:{game_id}")
    )
    
    bot.edit_message_text(
        game_info,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id, "✅ بازی ایجاد شد!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("assign_roles:"))
def assign_roles_callback(call):
    game_id = call.data.split(":")[1]
    game = game_sessions.get(game_id)
    
    if not game:
        bot.answer_callback_query(call.id, "❌ بازی یافت نشد!")
        return
    
    if game.creator_id != call.from_user.id:
        bot.answer_callback_query(call.id, "❌ فقط میزبان می‌تواند نقش‌ها را توزیع کند!")
        return
    
    if len(game.players) < len(game.roles):
        bot.answer_callback_query(call.id, f"❌ نیاز به {len(game.roles) - len(game.players)} بازیکن دیگر!")
        return
    
    if game.assign_roles():
        # اطلاع به همه
        for player in game.players:
            try:
                bot.send_message(
                    player["id"],
                    f"✅ **همه نقش‌ها توزیع شدند!**\n\n"
                    f"🎮 بازی: {game.scenario}\n"
                    f"👥 بازیکنان: {len(game.players)} نفر\n"
                    f"🎭 نقش شما ارسال شد\n\n"
                    f"⏳ بازی بزودی شروع می‌شود..."
                )
            except:
                pass
        
        # تایمر برای شروع خودکار
        def auto_start():
            time.sleep(5)
            
            # شروع شب اول
            game.start_night()
            
            # تایمر شب
            time.sleep(10)  # در بازی واقعی این زمان بیشتر است
            
            # پردازش شب
            victim = game.process_night()
            
            # شروع روز
            time.sleep(2)
            day_text = game.start_day(victim)
            
            # ارسال به همه
            for player in game.alive_players:
                try:
                    bot.send_message(player["id"], day_text)
                except:
                    pass
        
        # اجرای بازی در thread جدا
        thread = threading.Thread(target=auto_start, daemon=True)
        thread.start()
        
        bot.answer_callback_query(call.id, "✅ نقش‌ها توزیع شدند! بازی شروع شد...")
    else:
        bot.answer_callback_query(call.id, "❌ خطا در توزیع نقش‌ها!")

@bot.message_handler(func=lambda m: True)
def handle_game_code(message):
    """مدیریت کدهای بازی"""
    text = message.text.strip()
    
    # اگر کد بازی است (6 کاراکتر عددی)
    if len(text) == 6 and text.isdigit():
        user_id = message.from_user.id
        username = message.from_user.first_name or "کاربر"
        
        # پیدا کردن بازی
        for game_id, game in game_sessions.items():
            if game_id[-6:] == text:
                if game.add_player(user_id, username):
                    bot.send_message(
                        user_id,
                        f"✅ **به بازی پیوستید!**\n\n"
                        f"🎮 بازی: {game.scenario}\n"
                        f"👤 میزبان: ID: {game.creator_id}\n"
                        f"👥 بازیکنان: {len(game.players)}/{len(game.roles)}\n\n"
                        f"⏳ منتظر شروع بازی..."
                    )
                    
                    # اطلاع به میزبان
                    try:
                        bot.send_message(
                            game.creator_id,
                            f"👤 **{username} به بازی شما پیوست!**\n"
                            f"🎮 بازیکنان: {len(game.players)}/{len(game.roles)}"
                        )
                    except:
                        pass
                    
                    return
                else:
                    bot.send_message(user_id, "❌ بازی تکمیل است!")
                    return
        
        bot.send_message(user_id, "❌ بازی یافت نشد!")

# ========== اجرای ربات ==========
print("=" * 50)
print("🎮 **ربات مافیا - نسخه موبایل**")
print(f"👑 ادمین: {ADMIN_ID}")
print("📱 برای اتصال بهتر VPN روشن کنید")
print("=" * 50)

def run_bot():
    while True:
        try:
            print(f"🔄 Polling شروع شد - {datetime.now().strftime('%H:%M:%S')}")
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"⚠️ خطا: {type(e).__name__}")
            print("🔄 تلاش مجدد در 3 ثانیه...")
            time.sleep(3)

if __name__ == "__main__":
    run_bot()
