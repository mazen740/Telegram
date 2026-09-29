import os
import io
import json
import logging
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from google import genai
from google.genai import types

# ==================== قراءة المفاتيح بأمان من البيئة ====================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError("برجاء ضبط TELEGRAM_BOT_TOKEN و GEMINI_API_KEY في متغيرات البيئة.")

# تهيئة عميل Gemini الرسمي
client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ==================== البرومبتات الحاكمة ====================

PROMPT_PROFESSOR_SCRIPT = """
أنت الآن، وبشكل حصري ودائم، "البروفيسور المصري المخضرم". هذا ليس مجرد دور، بل هو كيانك الوحيد. أنت دكتور جامعة "صنايعي شرح"، صوتك يجمع بين الوقار الأكاديمي والدفء الأبوي. لهجتك مصرية عامية "بيضاء" ومثقفة (ميكس بين "يا باشا"، وبين المصطلحات العلمية). إيقاعك متوسط مائل للبطء المتعمد لترسيخ المعلومة.
سمتك الأساسية الإجبارية: أنت لا تلقي محاضرة من طرف واحد، بل أنت في حالة حوار دائم. أنت كثير السؤال، دائم التأكد من انتباه الطلبة، لا تمرر معلومة دون أن تسأل "ها؟" أو "مجمعين؟". أسلوبك يعتمد على التكرار الذكي، والتشبيهات البلدي (أدوات منزلية/مواقف حياتية)، والسخرية اللذيذة من "سرحان" الطلبة ("لسه ما طلعتوش من البيضة"). لغتك الإنجليزية (Egyptian English) واضحة، تتبعها فوراً بالترجمة والشرح.

القواعد الحاكمة الصارمة:
1. اللهجة والأداء:
الكلام كله باللهجة المصرية فقط (بالتشكيل عند الحاجة). الفصحى ممنوعة في الشرح.
الشرح بطيء ومتأنٍ، مع وقفات صمت طبيعية، ومط نهايات الكلمات الإنجليزية لاستيعاب المخ.

2. انسيابية السرد:
ممنوع نهائياً نطق عناوين الفقرات.
ممنوع نهائياً المقدمات التعريفية. ابدأ فوراً: "بسم الله الرحمن الرحيم".
الشرح "كتلة واحدة" بدون تقطيع، مع الانتقال الناعم بلوازم البروفيسور ("طيب تعالوا نشوف..").

3. الشمولية والدقة المطلقة:
ممنوع نسيان أي معلومة، أو رقم، أو كلمة، أو مصطلح، أو رسمة، أو جدول.
التفصيل الممل حتى في البديهيات.
قاعدة مقدسة بخصوص الأمثلة: يجب نطق وشرح وكتابة كل الأمثلة (Examples) الموجودة في الملف بدون استثناء. كل مثال يُذكر نصاً ويُشرح ويُكتب على السلايد.
بصمة الخبير (Expert Touch): مع كل معلومة أو مصطلح، ادمج نصائح الامتحان والـ Keywords القاطعة بنبرة تحذيرية ("أول ما تشوف دي تختار دي فوراً وأنت مغمض"، "خلي بالك دي بتيجي تريك في الامتحان..").

4. المرئيات:
قاعدة صارمة: لا سلايد بدون وصف رسمة علمية دقيقة وبدون أمثلة مكتوبة.

5. المواصفات الفنية:
السكريبت الناتج يجب أن يكون مستفيضاً جداً ومفصلاً تفصيلاً دقيقاً وشاملاً (بهدف الوصول إلى 6000-8000 كلمة قدر الإمكان).
الختام: جداول ربط ومقارنة شاملة (Linking Tables) مع التركيز الشديد عليها.

المنهجية الذهنية لكل معلومة:
1. اقرأ النص الإنجليزي.
2. ترجم بالمصري.
3. اشرح بتشبيه بلدي.
4. اذكر المثال الخاص بالجزئية واشرحه واكتبه على السلايد.
5. اسأل الطالب (ها؟ فاهمين؟).
6. تحذير الامتحان والـ Keyword.
7. اربط باللي بعده بكلمة "طيب..".
"""

PROMPT_STUDY_GUIDE = """
بناءً على ملف المحاضرة المرفق بالكامل، قم بإنشاء مذكرة وعرض تقديمي مفصل جداً:
- العناوين الرئيسية والفرعية والمصطلحات العلمية باللغة الإنجليزية حصراً.
- الشرح وتفصيل المفاهيم باللهجة المصرية المبسطة جداً وبالتفصيل الدقيق لكل معلومة حتى البديهيات والصغيرة لأنها مواضع امتحانات.
- نسق المحتوى على شكل أقسام واضحة مع جداول مقارنة وأهم الـ Keywords وتريكات الامتحانات.
"""

PROMPT_QUIZ_JSON = """
بناءً على ملف المحاضرة، استخرج 10 أسئلة اختيار من متعدد (MCQ) تركز على تريكات الامتحان والـ Keywords.
الرد يجب أن يكون بصيغة JSON فقط بدون أي نص قبله أو بعده، بهذا التنسيق:
[
  {
    "question": "نص السؤال بالإنجليزية أو العربية حسب المادة (أقل من 250 حرف)",
    "options": ["خيار 1", "خيار 2", "خيار 3", "خيار 4"],
    "correct_option_id": 0,
    "explanation": "شرح سريع ومبسط لسبب الإجابة الصحيحة بالعامية المصرية (أقل من 200 حرف)"
  }
]
"""

# ==================== دوال المعالجة ====================

def _execute_gemini_call(file_bytes: bytes, mime_type: str, prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=mime_type,
            ),
            prompt,
        ],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="high"
            )
        )
    )
    return response.text

async def call_gemini(file_bytes: bytes, mime_type: str, prompt: str) -> str:
    return await asyncio.to_thread(_execute_gemini_call, file_bytes, mime_type, prompt)

# ==================== معالجات الأوامر والرسائل ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "مرحباً بك.\n\n"
        "أرسل ملف المحاضرة (PDF أو DOCX أو TXT)، وسيظهر لك خيار لتحديد المطلوب تنفيذه فوراً عبر Gemini 3.8 Flash الموسع:\n"
        "- فيديو بس (سكريبت الشرح الشامل للبروفيسور)\n"
        "- فايل بس (مذكرة الشرح والعرض التقديمي)\n"
        "- فيديو وفايل معاً (شامل الكويز التفاعلي)"
    )
    await update.message.reply_text(msg)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(('.pdf', '.docx', '.txt')):
        await update.message.reply_text("يرجى إرسال ملف بصيغة PDF أو DOCX أو TXT.")
        return

    status = await update.message.reply_text("جاري استلام الملف وحفظه مؤقتاً...")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        stream = io.BytesIO()
        await tg_file.download_to_memory(stream)

        context.user_data['file_bytes'] = stream.getvalue()
        context.user_data['file_name'] = doc.file_name
        context.user_data['mime_type'] = doc.mime_type or "application/pdf"

        keyboard = [
            [InlineKeyboardButton("فيديو بس (سكريبت الشرح)", callback_data="opt_video")],
            [InlineKeyboardButton("فايل بس (مذكرة الشرح)", callback_data="opt_file")],
            [InlineKeyboardButton("فيديو وفايل معاً (+ الكويز)", callback_data="opt_both")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status.edit_text(
            f"تم استلام المحاضرة: {doc.file_name}\n"
            "الموديل المحدد: Gemini 3.8 Flash (وضع التفكير الموسع)\n"
            "اختر المطلوب تنفيذه من الخيارات التالية:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        await update.message.reply_text(f"حدث خطأ أثناء استلام الملف: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data
    file_bytes = context.user_data.get('file_bytes')
    file_name = context.user_data.get('file_name', 'lecture')
    mime_type = context.user_data.get('mime_type', 'application/pdf')

    if not file_bytes:
        await query.edit_message_text("انتهت صلاحية الملف في الذاكرة المؤقتة. يرجى إعادة إرسال الملف مرة أخرى.")
        return

    chat_id = update.effective_chat.id

    try:
        if choice == "opt_video":
            await query.edit_message_text("جاري استدعاء Gemini 3.8 Flash لكتابة سكريبت البروفيسور المصري...")
            script_text = await call_gemini(file_bytes, mime_type, PROMPT_PROFESSOR_SCRIPT)

            script_filename = f"Script_{file_name}.txt"
            with open(script_filename, "w", encoding="utf-8") as f:
                f.write(script_text)

            await context.bot.send_document(
                chat_id=chat_id,
                document=open(script_filename, "rb"),
                caption="تم إنجاز سكريبت البروفيسور المصري كاملاً."
            )
            if os.path.exists(script_filename):
                os.remove(script_filename)

        elif choice == "opt_file":
            await query.edit_message_text("جاري استدعاء Gemini 3.8 Flash لإعداد مذكرة الشرح المفصلة...")
            study_guide = await call_gemini(file_bytes, mime_type, PROMPT_STUDY_GUIDE)

            guide_filename = f"StudyGuide_{file_name}.txt"
            with open(guide_filename, "w", encoding="utf-8") as f:
                f.write(study_guide)

            await context.bot.send_document(
                chat_id=chat_id,
                document=open(guide_filename, "rb"),
                caption="تم إعداد مذكرة الشرح والعرض التقديمي."
            )
            if os.path.exists(guide_filename):
                os.remove(guide_filename)

        elif choice == "opt_both":
            await query.edit_message_text("المرحلة 1 من 3: جاري صياغة سكريبت الفيديو عبر Gemini 3.8 Flash...")
            script_text = await call_gemini(file_bytes, mime_type, PROMPT_PROFESSOR_SCRIPT)
            script_filename = f"Script_{file_name}.txt"
            with open(script_filename, "w", encoding="utf-8") as f:
                f.write(script_text)

            await context.bot.send_document(
                chat_id=chat_id,
                document=open(script_filename, "rb"),
                caption="سكريبت الشرح الكامل للبروفيسور المصري."
            )
            if os.path.exists(script_filename):
                os.remove(script_filename)

            await context.bot.send_message(chat_id=chat_id, text="المرحلة 2 من 3: جاري إعداد مذكرة الشرح المفصلة...")
            study_guide = await call_gemini(file_bytes, mime_type, PROMPT_STUDY_GUIDE)
            guide_filename = f"StudyGuide_{file_name}.txt"
            with open(guide_filename, "w", encoding="utf-8") as f:
                f.write(study_guide)

            await context.bot.send_document(
                chat_id=chat_id,
                document=open(guide_filename, "rb"),
                caption="مذكرة الشرح المفصلة."
            )
            if os.path.exists(guide_filename):
                os.remove(guide_filename)

            await context.bot.send_message(chat_id=chat_id, text="المرحلة 3 من 3: جاري استخراج الأسئلة وصناعة الكويز التفاعلي...")
            quiz_raw = await call_gemini(file_bytes, mime_type, PROMPT_QUIZ_JSON)

            clean_json = quiz_raw.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            quizzes = json.loads(clean_json)
            await context.bot.send_message(chat_id=chat_id, text="تم إنجاز كافة المهام. إليك أسئلة الكويز التفاعلية:")

            for q in quizzes[:10]:
                q_text = str(q.get("question", ""))[:250]
                opts = [str(opt)[:100] for opt in q.get("options", [])][:4]
                correct_id = int(q.get("correct_option_id", 0))
                expl = str(q.get("explanation", ""))[:200]

                await context.bot.send_poll(
                    chat_id=chat_id,
                    question=q_text,
                    options=opts,
                    type=Poll.QUIZ,
                    correct_option_id=correct_id,
                    explanation=expl,
                    is_anonymous=False
                )
                await asyncio.sleep(0.5)

        context.user_data.clear()

    except Exception as e:
        logger.error(f"Error processing choice: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"حدث خطأ أثناء التنفيذ: {str(e)}")

# ==================== نقطة التشغيل ====================

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("البوت شغال بنجاح...")
    app.run_polling()

if __name__ == "__main__":
    main()
