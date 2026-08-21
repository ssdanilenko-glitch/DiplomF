from . import commands, fsm, text, media, approval
# from . import admin, handoff, feedback  # временно отключены

def register_routers(dp):
    dp.include_router(commands.router)
    dp.include_router(fsm.router)
    dp.include_router(text.router)
    dp.include_router(media.router)
    dp.include_router(approval.router)
    # dp.include_router(admin.router)
    # dp.include_router(handoff.router)
    # dp.include_router(feedback.router)