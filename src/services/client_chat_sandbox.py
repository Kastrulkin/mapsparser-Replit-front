"""Explicit action boundaries for a sandbox that never dispatches to customers/staff."""
import re

HANDOFF_PREVIEW = 'В тестовом чате запрос сотруднику не отправляется. Здесь можно проверить сценарий передачи. Реальная передача выполняется через очередь «Сотруднику» в LocalOS: сотрудник должен отдельно принять диалог.'
BOOKING_PREVIEW = 'Тестовый чат не создаёт, не переносит и не отменяет записи. Можно уточнить услугу и пожелания; фактическую запись должен подтвердить администратор через проверенную систему записи.'


def action_preview(message):
    text = str(message).lower()
    if re.search(r'(позов|переда|свяж|связ|отправ|уведом).*(сотрудник|администратор|человек)|жив\w*\s+(администратор|человек|сотрудник)', text):
        return HANDOFF_PREVIEW
    if re.search(r'\b(запиши|запишите|перенеси|перенесите|отмени|отмените)\b', text):
        return BOOKING_PREVIEW
    return None


def guard_response(response):
    if re.search(r'(запрос|обращение|сообщение).{0,35}(передан|отправлен)|сотрудник.{0,15}уведомлен', str(response).lower().replace('ё','е')):
        return HANDOFF_PREVIEW
    if re.search(r'вы\s+записаны|запись\s+(подтверждена|создана|отменена|перенесена)', str(response).lower()):
        return BOOKING_PREVIEW
    return response
