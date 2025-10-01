from flask import Blueprint, request, jsonify

bp = Blueprint("jobs", __name__, url_prefix="/")


@bp.route("/start_job", methods=["POST"])
def start_job():
    payload = request.get_json(silent=True) or {}
    wallet = payload.get("wallet_address")
    networks = payload.get("networks", [])
    # Return a placeholder job id for scaffold
    return jsonify({"job_id": f"stub-{wallet or 'unknown'}"}), 200
