import telegram
from flask import Flask, request, jsonify
from flask_cors import CORS

from src.dayof.valentine_day_old import Web
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)


def create_app(bot: telegram.Bot):
    app = Flask(__name__)
    CORS(app)

    @app.route('/feb14/create', methods=['POST'])
    def index():
        body = request.get_json(silent=True)
        if 'text' in body and isinstance(body['text'], str) and \
                'heart_index' in body and isinstance(body['heart_index'], int):
            result = Web.create(bot, body['text'], body['heart_index'])
            return jsonify(**result)

        logger.error(f"[web_feb14] Can't create card. Body: {str(body)}")
        return jsonify(
            error=True,
            error_msg='Wrong body params',
        )

    @app.route('/feb14/card/<int:card_id>', methods=['POST'])
    def card(card_id: int):
        card = Web.get_card(card_id)
        if card:
            return jsonify(error=False, card=card)

        logger.error(f"[web_feb14] Card not found: {card_id}")
        return jsonify(
            error=True,
            error_msg='Валентинка не найдена',
        )

    @app.route('/feb14/cards', methods=['POST'])
    def cards():
        body = request.get_json(silent=True)
        if 'ids' in body:
            cards = Web.get_cards(body['ids'])
            return jsonify(error=False, cards=cards)
        return jsonify(
            error=False,
            cards=[],
        )

    return app


def start_server(bot, port):
    app = create_app(bot)
    app.run(debug=False, use_reloader=False, threaded=True, port=port)
