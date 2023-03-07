import asyncio
import logging
from os import getenv
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State 
from aiogram.types import Message, \
	ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton


load_dotenv()

TOKEN = getenv("TG_TOKEN")

router = Router()
bot = Bot(TOKEN, parse_mode="HTML")
dp = Dispatcher()

users_in_search = set()
users_chats = dict()
users_in_progress = dict()
idle_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Поиск")]], resize_keyboard=True)


class AnonymousChat(StatesGroup):
	idle = State()
	in_search = State()
	in_progress = State()
	complete = State()


@router.message(Command(commands=["start"]))
async def command_start_handler(message: Message, state: FSMContext) -> None:
	users_chats[message.from_user.id] = message.chat.id
	await message.answer(
		"Привет! Нажми кнопку «поиск», чтобы приступить к поиску собеседника.",
		reply_markup=idle_keyboard
	)
	await state.set_state(AnonymousChat.idle)


@router.message(AnonymousChat.idle, F.text == "Поиск")
async def command_search_handler(message: Message, state: FSMContext) -> None:
	in_search_keyboard = ReplyKeyboardMarkup(
		keyboard=[[KeyboardButton(text="Завершить поиск")]], resize_keyboard=True
	)
	in_progress_keyboard = ReplyKeyboardMarkup(
		keyboard=[[KeyboardButton(text="Завершить общение")]], resize_keyboard=True
	)
	user_id = message.from_user.id

	await state.set_state(AnonymousChat.in_search)
	await message.answer("Идет поиск собеседника.", reply_markup=in_search_keyboard)
	users_in_search.add(message.from_user.id)

	companion = None
	while user_id not in users_in_progress:
		potential_companions = users_in_search.difference(set([user_id]))
		if len(potential_companions):
			companion = potential_companions.pop()
			break
		await asyncio.sleep(0.2)

	if not companion:
		return

	users_in_search.remove(user_id)
	users_in_search.remove(companion)

	users_in_progress[message.from_user.id] = companion
	users_in_progress[companion] = message.from_user.id

	await bot.send_message(
		companion, "Собеседник найден. Вы можете общаться.",
		reply_markup=in_progress_keyboard
	)
	await message.answer(
		"Собеседник найден. Вы можете общаться.", reply_markup=in_progress_keyboard
	)

	companion_state = dp.fsm.resolve_context(
		bot, users_chats[companion], companion
	)
	await companion_state.set_state(AnonymousChat.in_progress)
	await state.set_state(AnonymousChat.in_progress)


@router.message(AnonymousChat.in_search, F.text == "Завершить поиск")
async def command_stop_search_handler(message: Message, state: FSMContext):
	user_id = message.chat.id

	users_in_search.remove(user_id)
	await message.answer(
		"Вы завершили поиск.", reply_markup=idle_keyboard
	)
	await state.set_state(AnonymousChat.idle)


@router.message(AnonymousChat.in_progress, F.text == "Завершить общение")
async def command_stop_chat_handler(message: Message, state: FSMContext):
	user_id = message.chat.id
	companion_id = users_in_progress[user_id]

	companion_state = dp.fsm.resolve_context(
		bot, users_chats[companion_id], companion_id
	)
	await companion_state.set_state(AnonymousChat.idle)

	await bot.send_message(
		users_in_progress[user_id], "Общение было завершено собеседником",
		reply_markup=idle_keyboard
	)
	await message.answer(
		"Вы завершили общение.", reply_markup=idle_keyboard
	)

	del users_in_progress[users_in_progress[user_id]]
	del users_in_progress[user_id]

	await state.set_state(AnonymousChat.idle)


@router.message(AnonymousChat.in_progress)
async def command_chat_handler(message: Message, state: FSMContext):
	user_id = message.chat.id
	try:
		await message.send_copy(
			chat_id=users_chats[users_in_progress[user_id]]
		)
	except TypeError:
		await message.answer("Отправка сообщений данного типа не поддерживается")


async def main() -> None:
	dp.include_router(router)
	await dp.start_polling(bot)


if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO)
	asyncio.run(main())
