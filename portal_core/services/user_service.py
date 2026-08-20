"""Regras de negócio de usuário que não devem ficar misturadas às rotas HTTP."""
from __future__ import annotations


def delete_user_and_related_data(db, models: dict[str, object], user) -> None:
    """Remove dados dependentes antes do usuário.

    A exclusão explícita funciona também em bancos antigos cujas constraints ainda não foram
    migradas para ON DELETE CASCADE.
    """
    user_id = user.id
    # Mensagens do agente são removidas por cascade ORM ao remover as conversas individualmente.
    conversation_model = models["AgentConversation"]
    for conversation in conversation_model.query.filter_by(user_id=user_id).all():
        db.session.delete(conversation)

    for name in (
        "ModuleAttempt",
        "EnglishTutorPreference",
        "EnglishTutorMessage",
        "EnglishTutorMistake",
        "EnglishTutorExercise",
        "EnglishPronunciationAttempt",
        "EnglishTranslationMemory",
        "EnglishCourseProgress",
        "EnglishStudyEvent",
    ):
        models[name].query.filter_by(user_id=user_id).delete(synchronize_session=False)

    db.session.delete(user)
    db.session.commit()
