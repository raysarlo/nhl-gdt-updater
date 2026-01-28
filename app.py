"""
NHL Game Day Thread (GDT) Updater - Web Application
Flask web app for generating Rangers game day threads.
"""

import os
from flask import Flask, render_template, request, jsonify

# Import the core GDT functionality
from nhl_gdt_updater import (
    get_team_abbrev,
    update_template,
    TEAM_FULL_NAMES,
    TEAM_MAPPINGS,
)

app = Flask(__name__)

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


@app.route('/')
def index():
    """Main page with team selection form."""
    teams = get_all_teams()
    return render_template('index.html', teams=teams)


@app.route('/generate', methods=['POST'])
def generate():
    """Generate the GDT HTML."""
    try:
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
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@app.route('/health')
def health():
    """Health check endpoint for Render."""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
