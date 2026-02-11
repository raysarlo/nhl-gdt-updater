"""
NHL Game Day Thread (GDT) Updater - Web Application
Flask web app for generating Rangers game day threads.
"""

import logging
import os
import secrets

from flask import Flask, render_template, request, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import the core GDT functionality
from nhl_gdt_updater import (
    get_team_abbrev,
    update_template,
    TEAM_FULL_NAMES,
    TEAM_MAPPINGS,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Rate limiting: 5 generates per minute per IP
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["60 per minute"],
    storage_uri="memory://",
)

# Path to the template file
TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), 'template.html')


def load_default_template():
    """Load the default template from template.html file."""
    try:
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return '<p>Error: template.html not found</p>'


def get_all_teams():
    """Get a sorted list of all teams for the dropdown."""
    teams = []
    seen = set()
    for abbrev in TEAM_FULL_NAMES:
        if abbrev != "NYR" and abbrev not in seen:
            seen.add(abbrev)
            teams.append({
                'abbrev': abbrev,
                'name': TEAM_FULL_NAMES[abbrev]
            })
    teams.sort(key=lambda x: x['name'])
    return teams


def generate_csrf_token():
    """Generate a CSRF token and store it in the session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


app.jinja_env.globals['csrf_token'] = generate_csrf_token


@app.route('/')
def index():
    """Main page with team selection form."""
    teams = get_all_teams()
    return render_template('index.html', teams=teams)


@app.route('/generate', methods=['POST'])
@limiter.limit("5 per minute")
def generate():
    """Generate the GDT HTML."""
    try:
        # CSRF validation
        token = request.form.get('_csrf_token', '')
        if not token or token != session.get('_csrf_token'):
            return jsonify({'error': 'Invalid or missing CSRF token. Please refresh the page.'}), 403

        opponent = request.form.get('opponent', '').strip()
        custom_template = request.form.get('template', '').strip()

        if not opponent:
            return jsonify({'error': 'Please select an opponent team'}), 400

        # Resolve team abbreviation
        opponent_abbrev = get_team_abbrev(opponent)
        if not opponent_abbrev:
            return jsonify({'error': f'Could not recognize team: {opponent}'}), 400

        if opponent_abbrev == "NYR":
            return jsonify({'error': 'Rangers cannot play themselves!'}), 400

        # Use custom template if provided, otherwise load from file
        template = custom_template if custom_template else load_default_template()

        # Generate the updated GDT
        result = update_template(template, opponent_abbrev)

        if not result:
            return jsonify({'error': 'Failed to generate GDT. Check the logs for details.'}), 500

        opponent_name = TEAM_FULL_NAMES.get(opponent_abbrev, opponent_abbrev)

        return jsonify({
            'success': True,
            'html': result,
            'opponent': opponent_name
        })

    except Exception as e:
        logger.exception("Error generating GDT")
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500


@app.route('/health')
def health():
    """Health check endpoint for Render."""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
