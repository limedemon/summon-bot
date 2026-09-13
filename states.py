from aiogram.fsm.state import State, StatesGroup


class AddSummon(StatesGroup):
    name = State()


class AddRarity(StatesGroup):
    name = State()
    chance = State()


class EditRarity(StatesGroup):
    name = State()
    chance = State()


class AddAdmin(StatesGroup):
    target = State()


class AddCard(StatesGroup):
    photo = State()
    name = State()
    rarity = State()
    exp = State()


class EditCard(StatesGroup):
    photo = State()
    name = State()
    exp = State()
