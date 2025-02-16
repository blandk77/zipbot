from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler

# Define the content for each callback
CB_ABOUT_TEXT = """
❍ ᴍʏ ɴᴀᴍᴇ : {bot_username}
❍ ʜᴏsᴛᴇᴅ ᴏɴ : ᴋᴏʏᴇʙ
❍ ᴅᴀᴛᴀʙᴀsᴇ : ᴍᴏɴɢᴏ ᴅʙ
❍ ʟᴀɴɢᴜᴀɢᴇ : ᴘʏᴛʜᴏɴ 𝟹
❍ ᴍʏ ᴄʀᴇᴀᴛᴏʀ : itsme

➻ Fᴏʀ ᴀɴʏ ᴅᴏᴜʙᴛ ᴀʙᴏᴜᴛ ᴜsᴇ ᴍᴇ, ᴄᴏɴᴛᴀᴄᴛ ᴏᴜʀ sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ ʙᴇʟᴏᴡ!?!
"""

CB_HELP_TEXT = """
Hᴏᴡ ᴛᴏ ᴜsᴇ ᴍᴇ?? 

Usᴇ /zip ᴡɪᴛʜ ᴀ ɴᴇᴡ ғɪʟᴇ ɴᴀᴍᴇ ᴡɪᴛʜᴏᴜᴛ ᴇxᴛᴇɴsɪᴏɴ 
/zip TG
Tʜɪs ᴡɪʟʟ ᴍᴀᴋᴇ ᴛʜᴇ ғɪʟᴇ ɴᴀᴍᴇ ᴀs "TG" ᴀɴᴅ ᴛʜᴇɴ sᴇɴᴅ ᴀʟʟ ᴛʜᴇ ғɪʟᴇs ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴢɪᴘ (ʙᴏᴛ ᴄᴜʀʀᴇɴᴛʟʏ sᴜᴘᴘᴏʀᴛs 2ɢʙ ᴏɴʟʏ). Sᴇɴᴅ /done ᴀғᴛᴇʀ sᴇɴᴅɪɴɢ ᴀʟʟ ᴛʜᴇ ғɪʟᴇs. Tʜᴇ ғɪʟᴇs ᴡɪʟʟ sᴛᴀʀᴛ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴀɴᴅ ᴜᴘʟᴏᴀᴅ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.
"""

CB_DONATE_TEXT = """
❤️‍      

💞  ɪꜰ ʏᴏᴜ ʟɪᴋᴇ ᴏᴜʀ ʙᴏᴛ ꜰᴇᴇʟ ꜰʀᴇᴇ ᴛᴏ ᴅᴏɴᴀᴛᴇ ᴀɴʏ ᴀᴍᴏᴜɴᴛ ₹𝟷𝟶, ₹𝟸𝟶, ₹𝟻𝟶, ₹𝟷𝟶𝟶, ᴇᴛᴄ.

❣️ 𝐷𝑜𝑛𝑎𝑡𝑖𝑜𝑛𝑠 𝑎𝑟𝑒 𝑟𝑒𝑎𝑙𝑙𝑦 𝑎𝑝𝑝𝑟𝑒𝑐𝑖𝑎𝑡𝑒𝑑 𝑖𝑡 ℎ𝑒𝑙𝑝𝑠 𝑖𝑛 𝑏𝑜𝑡 𝑑𝑒𝑣𝑒𝑙𝑜𝑝𝑚𝑒𝑛𝑡

💖 𝐔𝐏𝐈 𝐈𝐃 : 7305347700@pytes

💗 𝐐𝐑 𝐂𝐨𝐝𝐞 : 𝖢𝗅𝗂𝖼𝗄 𝖧𝖾𝗋𝖾
"""

# Define callback data (used to identify which button was pressed)
ABOUT_CALLBACK_DATA = "about_callback"
HELP_CALLBACK_DATA = "help_callback"
DONATE_CALLBACK_DATA = "donate_callback"

# Function to create the inline keyboard
def create_keyboard():
    keyboard = [
        [InlineKeyboardButton("About", callback_data=ABOUT_CALLBACK_DATA)],
        [InlineKeyboardButton("Help", callback_data=HELP_CALLBACK_DATA)],
        [InlineKeyboardButton("Donate", callback_data=DONATE_CALLBACK_DATA)],
    ]
    return InlineKeyboardMarkup(keyboard)


# Callback query handlers
def about_callback(update, context):
    query = update.callback_query
    query.answer()  # Acknowledge the callback
    bot_username = context.bot.username # Access the bot's username
    text = CB_ABOUT_TEXT.format(bot_username=bot_username) # Insert into the string
    query.edit_message_text(text, parse_mode="HTML")

def help_callback(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(CB_HELP_TEXT, parse_mode="HTML")

def donate_callback(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text(CB_DONATE_TEXT, parse_mode="HTML", disable_web_page_preview=True) #Added disable_web_page_preview


# Function to register the callback handlers
def register_callbacks(dispatcher):
    dispatcher.add_handler(CallbackQueryHandler(about_callback, pattern=ABOUT_CALLBACK_DATA))
    dispatcher.add_handler(CallbackQueryHandler(help_callback, pattern=HELP_CALLBACK_DATA))
    dispatcher.add_handler(CallbackQueryHandler(donate_callback, pattern=DONATE_CALLBACK_DATA))
