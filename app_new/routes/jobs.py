from flask import Blueprint, request, jsonify

bp = Blueprint("jobs", __name__, url_prefix="/")


@bp.route("/start_job", methods=["POST"])
def start_job():
    payload = request.get_json(silent=True) or {}
    wallet = payload.get("wallet_address") or payload.get('wallet')
    networks = payload.get("networks", ['arbitrum'])

    # Prefer delegation to the running monolith app so jobs actually run and results get stored.
    try:
        import importlib
        import threading
        app_mod = importlib.import_module('app')
        # Use the monolith's _init_job and process_job to start the background work in-process.
        if hasattr(app_mod, '_init_job') and hasattr(app_mod, 'process_job'):
            job_id = app_mod._init_job(wallet, networks)
            t = threading.Thread(target=app_mod.process_job, args=(job_id, wallet, networks), daemon=True)
            t.start()
            return jsonify({'job_id': job_id}), 200
    except Exception:
        # If delegation fails, fall through to the stub below
        pass

    # Fallback: return a stub job id to avoid breaking the frontend during incremental migration
    return jsonify({"job_id": f"stub-{wallet or 'unknown'}"}), 200
