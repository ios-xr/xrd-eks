# noxfile.py


import nox


@nox.session
def test(session: nox.Session) -> None:
    session.install("--upgrade", "pip")
    session.install("-r", "requirements.txt")
    session.run("pytest", *session.posargs)
