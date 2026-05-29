from portal import application

if __name__ == "__main__":
    import os
    from werkzeug.serving import run_simple

    run_simple(
        "0.0.0.0",
        int(os.getenv("PORT", "5000")),
        application,
        use_debugger=os.getenv("FLASK_DEBUG", "0") == "1",
        use_reloader=False,
    )
