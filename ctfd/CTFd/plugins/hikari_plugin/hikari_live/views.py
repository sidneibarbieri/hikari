from flask import jsonify, render_template

from CTFd.utils.decorators.visibility import check_account_visibility, check_score_visibility

from .queries import build_live_board


@check_account_visibility
@check_score_visibility
def live_board():
    return render_template("hikari-live.html", board=build_live_board())


@check_account_visibility
@check_score_visibility
def live_data():
    return jsonify(build_live_board().dict())
