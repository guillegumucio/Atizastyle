
#TELEGRAM_TOKEN = '7620105166:AAGPbrynwVxX2TX7xMPlWZQBa5yKtLOPqUk'
#otro token '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'
import logging
import asyncio
import nest_asyncio
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

from diffusers import AutoPipelineForText2Image
import torch

# === CONFIGURACIÓN ===
TELEGRAM_TOKEN = '7620105166:AAGPbrynwVxX2TX7xMPlWZBa5yKtLOPqUk'

# === ESTADOS DE CONVERSACIÓN ===
SELECCION_ESTILO, INGRESAR_PROMPT, MOSTRAR_IMAGEN = range(3)

# === LOGGING ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# === VARIABLES TEMPORALES ===
estilos = {}
prompts = {}

# === CARGAR PIPELINE DE KANDINSKY ===
print("⚙️ Cargando modelo Kandinsky localmente. Esto puede tardar un poco...")
pipe = AutoPipelineForText2Image.from_pretrained(
    "kandinsky-community/kandinsky-2-2-decoder", torch_dtype=torch.float16
)
device = "cuda" if torch.cuda.is_available() else "cpu"
pipe = pipe.to(device)
print(f"✅ Modelo cargado en {device}")

# === FUNCION PARA GENERAR IMAGEN ===
def generar_imagen_kandinsky(prompt: str, negative_prompt: str = "low quality, bad quality") -> BytesIO:
    image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        prior_guidance_scale=1.0,
        height=768,
        width=768
    ).images[0]
    bio = BytesIO()
    image.save(bio, format="PNG")
    bio.seek(0)
    return bio

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎨 Crear diseño nuevo", callback_data="nuevo_diseño")]]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔥 ¡Bienvenido al *Creador de Poleras AtizaStyle*!\n\n¿Quieres comenzar?",
        reply_markup=markup, parse_mode="Markdown"
    )

# === PASO 1: SELECCIÓN DE ESTILO ===
async def nuevo_diseño(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    teclado = [
        [InlineKeyboardButton("🌿 Natural", callback_data="Natural"),
         InlineKeyboardButton("🔥 Abstracto", callback_data="Abstracto")],
        [InlineKeyboardButton("✨ Fantasía", callback_data="Fantasía"),
         InlineKeyboardButton("🎴 Minimalista", callback_data="Minimalista")],
        [InlineKeyboardButton("🤖 Cyberpunk", callback_data="Cyberpunk")]
    ]
    await query.edit_message_text(
        "🎨 *Paso 1:* Elige un estilo para tu diseño",
        reply_markup=InlineKeyboardMarkup(teclado), parse_mode="Markdown"
    )
    return SELECCION_ESTILO

# === PASO 2: INGRESO DE PROMPT ===
async def elegir_estilo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    estilo = query.data
    estilos[query.from_user.id] = estilo
    await query.answer()
    await query.edit_message_text(
        f"📝 *Paso 2:* Escribe una idea para tu diseño.\n\n_Ejemplo: 'un colibrí de fuego sobre un bosque al atardecer'_",
        parse_mode="Markdown"
    )
    return INGRESAR_PROMPT

# === GENERAR IMAGEN ===
async def recibir_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    user_id = update.effective_user.id
    estilo = estilos.get(user_id, "")
    prompt_final = f"{prompt}, estilo {estilo}"
    prompts[user_id] = prompt_final

    await update.message.reply_text("🎨 Generando tu diseño con IA localmente... Esto puede tardar unos segundos...")

    try:
        bio = await asyncio.to_thread(generar_imagen_kandinsky, prompt_final)
        context.user_data['image_bytes'] = bio.read()  # Guardar bytes para posible reutilización

        bio.seek(0)
        botones = [
            [InlineKeyboardButton("✅ Usar este diseño", callback_data="usar")],
            [InlineKeyboardButton("🔁 Generar otra", callback_data="otra"),
             InlineKeyboardButton("✍️ Cambiar idea", callback_data="cambiar")]
        ]

        await update.message.reply_photo(
            photo=bio,
            caption="🖼️ Aquí tienes tu diseño.\n\n¿Qué te gustaría hacer ahora?",
            reply_markup=InlineKeyboardMarkup(botones)
        )
        return MOSTRAR_IMAGEN

    except Exception as e:
        await update.message.reply_text(f"❗️ Error generando imagen: {e}")
        return ConversationHandler.END

# === BOTONES POST-IMAGEN ===
async def acciones_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    accion = query.data

    if accion == "usar":
        await query.edit_message_caption(
            caption="✅ ¡Perfecto! Este diseño ha sido guardado.\n\n👕 ¿Te gustaría encargar una polera con este diseño?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Encargar ahora", callback_data="encargar")],
                [InlineKeyboardButton("🔙 Volver al inicio", callback_data="volver")]
            ])
        )
        return MOSTRAR_IMAGEN

    elif accion == "encargar":
        # Aquí puedes implementar la lógica para guardar pedido o enviar la imagen a ti mismo
        image_bytes = context.user_data.get('image_bytes')
        if image_bytes:
            # Envía la imagen a tu telegram
            chat_id_negocio = '1593471631'  # <- Aquí pon tu chat ID de Telegram (puedes obtenerlo con @userinfobot)
            await context.bot.send_photo(chat_id=chat_id_negocio, photo=BytesIO(image_bytes),
                                         caption=f"Nuevo pedido de {update.effective_user.full_name}")
        await query.edit_message_caption("✅ Pedido recibido. ¡Gracias por confiar en nosotros!")
        return ConversationHandler.END

    elif accion == "otra":
        prompt_final = prompts.get(user_id, "")
        await query.edit_message_caption("🔄 Generando nueva variación...")

        try:
            bio = await asyncio.to_thread(generar_imagen_kandinsky, prompt_final)
            context.user_data['image_bytes'] = bio.read()

            bio.seek(0)
            botones = [
                [InlineKeyboardButton("✅ Usar este diseño", callback_data="usar")],
                [InlineKeyboardButton("🔁 Generar otra", callback_data="otra"),
                 InlineKeyboardButton("✍️ Cambiar idea", callback_data="cambiar")]
            ]
            await query.edit_message_media(
                media=InputMediaPhoto(media=bio, caption="🎨 Aquí tienes una nueva variación. ¿Te gusta esta?"),
                reply_markup=InlineKeyboardMarkup(botones)
            )
            return MOSTRAR_IMAGEN
        except Exception as e:
            await query.edit_message_caption(f"❗️ Error generando imagen: {e}")
            return ConversationHandler.END

    elif accion == "cambiar":
        await query.edit_message_caption("✍️ Escribe una nueva idea para tu diseño.")
        return INGRESAR_PROMPT

    elif accion == "volver":
        return await nuevo_diseño(update, context)

# === CANCELAR ===
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Has cancelado el diseño. Usa /start para comenzar de nuevo.")
    return ConversationHandler.END

# === MAIN ===
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(nuevo_diseño, pattern="^nuevo_diseño$")],
        states={
            SELECCION_ESTILO: [CallbackQueryHandler(elegir_estilo)],
            INGRESAR_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_prompt)],
            MOSTRAR_IMAGEN: [CallbackQueryHandler(acciones_imagen)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    print("🤖 Bot ejecutándose...")
    await app.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
