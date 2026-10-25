"""
Admin routes - dashboard, teams, players, matches, fixtures, result entry.
"""

from datetime import datetime, date
from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    abort,
)
from flask_login import login_required, current_user

from app.blueprints.admin import admin_bp
from app.extensions import db
from sqlalchemy import or_
from app.models import (
    User,
    Role,
    Season,
    Team,
    Player,
    Match,
    MatchEvent,
    AuditLog,
    Gallery,
    FanComment,
    Visitor,
)
from app.decorators import admin_required, stats_manager_required
from app.services.match_service import MatchService
from app.services.visitor_service import get_visitor_stats
from app.utils import allowed_file, upload_image


# --- Dashboard ---


@admin_bp.route("/")
@login_required
def dashboard():
    """Admin dashboard."""
    return render_template("admin/dashboard.html")


@admin_bp.route("/analytics")
@admin_required
def analytics():
    """Visitor analytics dashboard."""
    stats = get_visitor_stats()
    return render_template("admin/analytics.html", stats=stats)


# --- Seasons ---


@admin_bp.route("/seasons")
@admin_required
def seasons():
    """List seasons."""
    seasons = Season.query.order_by(Season.start_date.desc()).all()
    return render_template("admin/seasons.html", seasons=seasons)


@admin_bp.route("/seasons/add", methods=["GET", "POST"])
@admin_required
def add_season():
    """Add season."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start = request.form.get("start_date")
        end = request.form.get("end_date")
        is_active = request.form.get("is_active") == "on"
        if name and start and end:
            season = Season(
                name=name,
                start_date=datetime.strptime(start, "%Y-%m-%d").date(),
                end_date=datetime.strptime(end, "%Y-%m-%d").date(),
                is_active=is_active,
            )
            if is_active:
                for s in Season.query.all():
                    s.is_active = False
            db.session.add(season)
            db.session.commit()
            _audit("create", "Season", season.id, f"Created season {name}")
            flash("Season added.", "success")
            return redirect(url_for("admin.seasons"))
        flash("Invalid data.", "danger")
    return render_template("admin/season_form.html", season=None)


# --- Teams ---


@admin_bp.route("/teams")
@admin_required
def teams():
    """List teams with search."""
    q = Team.query
    search = request.args.get("q", "").strip()
    if search:
        q = q.filter(
            or_(Team.name.ilike(f"%{search}%"), Team.short_name.ilike(f"%{search}%"))
        )
    page = request.args.get("page", 1, type=int)
    teams = q.order_by(Team.name).paginate(
        page=page,
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    return render_template("admin/teams.html", teams=teams, search=search)


@admin_bp.route("/teams/add", methods=["GET", "POST"])
@admin_required
def add_team():
    """Add team with logo upload."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        short_name = request.form.get("short_name", "").strip() or None
        founded = request.form.get("founded_year", type=int) or None
        stadium = request.form.get("stadium", "").strip() or None

        if name:
            team = Team(
                name=name,
                short_name=short_name,
                founded_year=founded,
                stadium=stadium,
            )
            db.session.add(team)
            db.session.flush()

            logo = request.files.get("logo")
            if logo and logo.filename and allowed_file(logo.filename, current_app.config["ALLOWED_EXTENSIONS"]):
                url_or_fn = upload_image(
                    logo, current_app.config["TEAM_LOGOS_FOLDER"], f"team_{team.id}", current_app
                )
                if url_or_fn:
                    team.logo_filename = url_or_fn

            db.session.commit()
            _audit("create", "Team", team.id, f"Added team {name}")
            flash("Team added.", "success")
            return redirect(url_for("admin.teams"))
        flash("Team name required.", "danger")
    return render_template("admin/team_form.html", team=None)


@admin_bp.route("/teams/<int:team_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_team(team_id):
    """Edit team."""
    team = Team.query.get_or_404(team_id)
    if request.method == "POST":
        team.name = request.form.get("name", "").strip() or team.name
        team.short_name = request.form.get("short_name", "").strip() or None
        team.founded_year = request.form.get("founded_year", type=int) or None
        team.stadium = request.form.get("stadium", "").strip() or None

        logo = request.files.get("logo")
        if logo and logo.filename and allowed_file(logo.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            url_or_fn = upload_image(
                logo, current_app.config["TEAM_LOGOS_FOLDER"], f"team_{team.id}", current_app
            )
            if url_or_fn:
                team.logo_filename = url_or_fn

        db.session.commit()
        _audit("update", "Team", team.id, f"Updated team {team.name}")
        flash("Team updated.", "success")
        return redirect(url_for("admin.teams"))
    return render_template("admin/team_form.html", team=team)


@admin_bp.route("/teams/<int:team_id>/delete", methods=["POST"])
@admin_required
def delete_team(team_id):
    """Delete team."""
    team = Team.query.get_or_404(team_id)
    name = team.name
    db.session.delete(team)
    db.session.commit()
    _audit("delete", "Team", team_id, f"Deleted team {name}")
    flash("Team deleted.", "success")
    return redirect(url_for("admin.teams"))


# --- Players ---


@admin_bp.route("/players")
@admin_required
def players():
    """List players with search."""
    q = Player.query.join(Team)
    search = request.args.get("q", "").strip()
    if search:
        q = q.filter(
            or_(
                Player.first_name.ilike(f"%{search}%"),
                Player.last_name.ilike(f"%{search}%"),
                Team.name.ilike(f"%{search}%"),
            )
        )
    page = request.args.get("page", 1, type=int)
    players = q.order_by(Player.last_name).paginate(
        page=page,
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    return render_template("admin/players.html", players=players, search=search)


@admin_bp.route("/players/add", methods=["GET", "POST"])
@admin_required
def add_player():
    """Register player."""
    teams = Team.query.order_by(Team.name).all()
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        team_id = request.form.get("team_id", type=int)
        position = request.form.get("position", "MID")
        jersey = request.form.get("jersey_number", type=int) or None

        if first_name and last_name and team_id:
            age = request.form.get("age", type=int) or None
            player = Player()
            player.first_name = first_name
            player.last_name = last_name
            player.team_id = team_id
            player.position = position
            player.jersey_number = jersey
            player.age = age
            db.session.add(player)
            db.session.flush()

            photo = request.files.get("photo")
            if photo and photo.filename and allowed_file(photo.filename, current_app.config["ALLOWED_EXTENSIONS"]):
                url_or_fn = upload_image(
                    photo, current_app.config["PLAYER_PHOTOS_FOLDER"], f"player_{player.id}", current_app
                )
                if url_or_fn:
                    player.photo_filename = url_or_fn

            db.session.commit()
            _audit("create", "Player", player.id, f"Registered {player.full_name}")
            flash("Player registered.", "success")
            return redirect(url_for("admin.players"))
        flash("First name, last name and team required.", "danger")
    return render_template("admin/player_form.html", player=None, teams=teams)


@admin_bp.route("/players/<int:player_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_player(player_id):
    """Edit player."""
    player = Player.query.get_or_404(player_id)
    teams = Team.query.order_by(Team.name).all()
    if request.method == "POST":
        player.first_name = request.form.get("first_name", "").strip() or player.first_name
        player.last_name = request.form.get("last_name", "").strip() or player.last_name
        player.team_id = request.form.get("team_id", type=int) or player.team_id
        player.position = request.form.get("position", player.position)
        player.jersey_number = request.form.get("jersey_number", type=int) or None
        player.age = request.form.get("age", type=int) or None

        photo = request.files.get("photo")
        if photo and photo.filename and allowed_file(photo.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            url_or_fn = upload_image(
                photo, current_app.config["PLAYER_PHOTOS_FOLDER"], f"player_{player.id}", current_app
            )
            if url_or_fn:
                player.photo_filename = url_or_fn

        db.session.commit()
        _audit("update", "Player", player.id, f"Updated {player.full_name}")
        flash("Player updated.", "success")
        return redirect(url_for("admin.players"))
    return render_template("admin/player_form.html", player=player, teams=teams)


# --- Fixtures ---


@admin_bp.route("/fixtures")
@stats_manager_required
def fixtures():
    """List fixtures by season and matchday."""
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        season = Season.query.order_by(Season.start_date.desc()).first()

    matches = []
    if season:
        matchday = request.args.get("matchday", type=int)
        q = Match.query.filter_by(season_id=season.id).order_by(Match.matchday, Match.kickoff)
        if matchday:
            q = q.filter_by(matchday=matchday)
        matches = q.all()

    return render_template("admin/fixtures.html", season=season, matches=matches)


@admin_bp.route("/fixtures/add", methods=["GET", "POST"])
@stats_manager_required
def add_fixture():
    """Schedule fixture."""
    seasons = Season.query.order_by(Season.start_date.desc()).all()
    teams = Team.query.order_by(Team.name).all()

    if request.method == "POST":
        season_id = request.form.get("season_id", type=int)
        matchday = request.form.get("matchday", type=int)
        home_team_id = request.form.get("home_team_id", type=int)
        away_team_id = request.form.get("away_team_id", type=int)
        kickoff_str = request.form.get("kickoff")

        if season_id and matchday and home_team_id and away_team_id and kickoff_str and home_team_id != away_team_id:
            season = Season.query.get(season_id)
            home_team = Team.query.get(home_team_id)
            away_team = Team.query.get(away_team_id)
            if season and home_team and away_team:
                # Ensure teams are in season
                if home_team not in season.teams:
                    season.teams.append(home_team)
                if away_team not in season.teams:
                    season.teams.append(away_team)
            kickoff = datetime.strptime(kickoff_str, "%Y-%m-%dT%H:%M")
            match = Match(
                season_id=season_id,
                matchday=matchday,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                kickoff=kickoff,
            )
            db.session.add(match)
            db.session.commit()
            _audit("create", "Match", match.id, f"Scheduled fixture {matchday}")
            flash("Fixture scheduled.", "success")
            return redirect(url_for("admin.fixtures"))
        flash("Invalid fixture data.", "danger")

    return render_template("admin/fixture_form.html", seasons=seasons, teams=teams)


@admin_bp.route("/fixtures/<int:match_id>/edit", methods=["GET", "POST"])
@stats_manager_required
def edit_fixture(match_id):
    """Edit fixture details (before result entry)."""
    match = Match.query.get_or_404(match_id)
    
    # Only allow editing if match hasn't been played yet
    if match.is_played:
        flash("Cannot edit fixture after result has been entered.", "warning")
        return redirect(url_for("admin.fixtures"))
    
    seasons = Season.query.order_by(Season.start_date.desc()).all()
    teams = Team.query.order_by(Team.name).all()

    if request.method == "POST":
        season_id = request.form.get("season_id", type=int)
        matchday = request.form.get("matchday", type=int)
        home_team_id = request.form.get("home_team_id", type=int)
        away_team_id = request.form.get("away_team_id", type=int)
        kickoff_str = request.form.get("kickoff")

        if season_id and matchday and home_team_id and away_team_id and kickoff_str and home_team_id != away_team_id:
            season = Season.query.get(season_id)
            home_team = Team.query.get(home_team_id)
            away_team = Team.query.get(away_team_id)
            if season and home_team and away_team:
                # Ensure teams are in season
                if home_team not in season.teams:
                    season.teams.append(home_team)
                if away_team not in season.teams:
                    season.teams.append(away_team)
            
            kickoff = datetime.strptime(kickoff_str, "%Y-%m-%dT%H:%M")
            
            # Update match details
            match.season_id = season_id
            match.matchday = matchday
            match.home_team_id = home_team_id
            match.away_team_id = away_team_id
            match.kickoff = kickoff
            
            db.session.commit()
            _audit("update", "Match", match.id, f"Updated fixture {matchday}")
            flash("Fixture updated successfully.", "success")
            return redirect(url_for("admin.fixtures"))
        flash("Invalid fixture data.", "danger")

    return render_template("admin/fixture_form.html", seasons=seasons, teams=teams, match=match)


# --- Result Entry ---


@admin_bp.route("/fixtures/<int:match_id>/result", methods=["GET", "POST"])
@stats_manager_required
def enter_result(match_id):
    """Enter match result and events."""
    match = Match.query.get_or_404(match_id)
    home_players = Player.query.filter_by(team_id=match.home_team_id).order_by(Player.jersey_number).all()
    away_players = Player.query.filter_by(team_id=match.away_team_id).order_by(Player.jersey_number).all()

    if request.method == "POST":
        home_goals = request.form.get("home_goals", type=int)
        away_goals = request.form.get("away_goals", type=int)
        if home_goals is None:
            home_goals = 0
        if away_goals is None:
            away_goals = 0

        events = []
        # Parse events from form (event_0_type, event_0_minute, event_0_player_id, etc.)
        i = 0
        while True:
            ev_type = request.form.get(f"event_{i}_type")
            if not ev_type:
                break
            goal_scorer_id = request.form.get(f"event_{i}_goal_scorer_id", type=int)
            player_id = request.form.get(f"event_{i}_player_id", type=int)
            if ev_type == MatchEvent.TYPE_GOAL:
                player_id = goal_scorer_id or player_id
            ev = {
                "event_type": ev_type,
                "minute": request.form.get(f"event_{i}_minute", type=int) or 0,
                "extra_time": request.form.get(f"event_{i}_extra_time", type=int),
                "player_id": player_id,
            }
            if ev_type == MatchEvent.TYPE_GOAL:
                ev["goal_scorer_id"] = goal_scorer_id or player_id
                ev["assist_id"] = request.form.get(f"event_{i}_assist_id", type=int)
                ev["is_penalty"] = request.form.get(f"event_{i}_is_penalty") == "on"
                ev["is_own_goal"] = request.form.get(f"event_{i}_is_own_goal") == "on"
            elif ev_type == MatchEvent.TYPE_SUBSTITUTION:
                ev["player_off_id"] = request.form.get(f"event_{i}_player_off_id", type=int)
                ev["player_on_id"] = request.form.get(f"event_{i}_player_on_id", type=int)
            if ev.get("player_id") or ev.get("goal_scorer_id") or (ev_type == MatchEvent.TYPE_SUBSTITUTION and ev.get("player_off_id") and ev.get("player_on_id")):
                events.append(ev)
            i += 1

        try:
            MatchService.record_match_result(match_id, home_goals, away_goals, events)
            _audit("update", "Match", match_id, f"Recorded result {home_goals}-{away_goals}")
            flash("Result recorded. Stats updated.", "success")
            return redirect(url_for("admin.fixtures"))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")

    return render_template(
        "admin/result_form.html",
        match=match,
        home_players=home_players,
        away_players=away_players,
        MatchEvent=MatchEvent,
    )


def _audit(action: str, entity_type: str, entity_id: int, details: str):
    """Log admin action."""
    log = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        user_id=current_user.id,
        ip_address=request.remote_addr,
    )
    db.session.add(log)


# --- Gallery ---


@admin_bp.route("/gallery")
@admin_required
def gallery():
    """List gallery items."""
    q = Gallery.query
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    
    if search:
        q = q.filter(
            or_(
                Gallery.title.ilike(f"%{search}%"),
                Gallery.description.ilike(f"%{search}%")
            )
        )
    
    if category:
        q = q.filter_by(category=category)
    
    page = request.args.get("page", 1, type=int)
    galleries = q.order_by(Gallery.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    
    # Get categories for filter
    categories = db.session.query(Gallery.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    return render_template(
        "admin/gallery.html",
        galleries=galleries,
        categories=categories,
        current_category=category,
        search=search
    )


@admin_bp.route("/gallery/add", methods=["GET", "POST"])
@admin_required
def add_gallery():
    """Add gallery item."""
    matches = Match.query.order_by(Match.kickoff.desc()).limit(50).all()
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "highlight")
        match_id = request.form.get("match_id", type=int) or None
        is_featured = request.form.get("is_featured") == "on"
        
        if title:
            gallery = Gallery(
                title=title,
                description=description,
                category=category,
                match_id=match_id,
                is_featured=is_featured,
            )
            db.session.add(gallery)
            db.session.flush()

            image = request.files.get("image")
            if image and image.filename and allowed_file(image.filename, current_app.config["ALLOWED_EXTENSIONS"]):
                url_or_fn = upload_image(
                    image, current_app.config["GALLERY_FOLDER"], f"gallery_{gallery.id}", current_app
                )
                if url_or_fn:
                    gallery.image_filename = url_or_fn

            db.session.commit()
            _audit("create", "Gallery", gallery.id, f"Added gallery item {title}")
            flash("Gallery item added.", "success")
            return redirect(url_for("admin.gallery"))
        flash("Title is required.", "danger")
    
    return render_template("admin/gallery_form.html", gallery=None, matches=matches)


@admin_bp.route("/gallery/<int:gallery_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_gallery(gallery_id):
    """Edit gallery item."""
    gallery = Gallery.query.get_or_404(gallery_id)
    matches = Match.query.order_by(Match.kickoff.desc()).limit(50).all()
    
    if request.method == "POST":
        gallery.title = request.form.get("title", "").strip() or gallery.title
        gallery.description = request.form.get("description", "").strip() or gallery.description
        gallery.category = request.form.get("category", gallery.category)
        gallery.match_id = request.form.get("match_id", type=int) or None
        gallery.is_featured = request.form.get("is_featured") == "on"

        image = request.files.get("image")
        if image and image.filename and allowed_file(image.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            url_or_fn = upload_image(
                image, current_app.config["GALLERY_FOLDER"], f"gallery_{gallery.id}", current_app
            )
            if url_or_fn:
                gallery.image_filename = url_or_fn

        db.session.commit()
        _audit("update", "Gallery", gallery.id, f"Updated gallery item {gallery.title}")
        flash("Gallery item updated.", "success")
        return redirect(url_for("admin.gallery"))
    
    return render_template("admin/gallery_form.html", gallery=gallery, matches=matches)


@admin_bp.route("/gallery/<int:gallery_id>/delete", methods=["POST"])
@admin_required
def delete_gallery(gallery_id):
    """Delete gallery item."""
    gallery = Gallery.query.get_or_404(gallery_id)
    title = gallery.title
    db.session.delete(gallery)
    db.session.commit()
    _audit("delete", "Gallery", gallery_id, f"Deleted gallery item {title}")
    flash("Gallery item deleted.", "success")
    return redirect(url_for("admin.gallery"))


# --- Fan Comments ---


@admin_bp.route("/fan-comments")
@admin_required
def fan_comments():
    """Manage fan comments."""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "").strip()
    
    q = FanComment.query
    
    if search:
        q = q.filter(
            or_(
                FanComment.name.ilike(f"%{search}%"),
                FanComment.nickname.ilike(f"%{search}%"),
                FanComment.comment.ilike(f"%{search}%")
            )
        )
    
    comments = q.order_by(FanComment.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config["ITEMS_PER_PAGE"],
        error_out=False,
    )
    
    return render_template(
        "admin/fan_comments.html",
        comments=comments,
        search=search
    )


@admin_bp.route("/fan-comments/<int:comment_id>/delete", methods=["POST"])
@admin_required
def delete_fan_comment(comment_id):
    """Delete a fan comment."""
    comment = FanComment.query.get_or_404(comment_id)
    comment_text = comment.comment[:50] + "..." if len(comment.comment) > 50 else comment.comment
    
    db.session.delete(comment)
    db.session.commit()
    _audit("delete", "FanComment", comment_id, f"Deleted fan comment: {comment_text}")
    flash("Fan comment deleted successfully.", "success")
    return redirect(url_for("admin.fan_comments"))
