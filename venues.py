"""Stadium/venue name lookup — static mapping for common opponents."""

# Mapping: team shortName (from football-data.org) → stadium name
# Covers La Liga 2025/26 + common Champions League opponents
VENUE_MAP = {
    # La Liga
    "Real Madrid": "Estadio Santiago Bernabéu",
    "Atleti": "Estadio Metropolitano",
    "Athletic": "San Mamés",
    "Sevilla FC": "Ramón Sánchez-Pizjuán",
    "Real Sociedad": "Anoeta Stadium",
    "Real Betis": "Estadio Benito Villamarín",
    "Villarreal": "Estadio de la Cerámica",
    "Valencia": "Mestalla Stadium",
    "Celta": "Estadio de Balaídos",
    "Osasuna": "Estadio El Sadar",
    "Mallorca": "Estadio Mallorca Son Moix",
    "Getafe": "Coliseum Alfonso Pérez",
    "Girona": "Estadio Montilivi",
    "Rayo Vallecano": "Estadio de Vallecas",
    "Alavés": "Estadio de Mendizorroza",
    "Elche": "Estadio Manuel Martínez Valero",
    "Levante": "Estadio Ciudad de Valencia",
    "Espanyol": "RCDE Stadium",
    "Real Oviedo": "Estadio Carlos Tartiere",
    # Barcelona itself
    "Barça": "Spotify Camp Nou",
    "Barcelona": "Spotify Camp Nou",
    # Champions League
    "PSG": "Parc des Princes",
    "Chelsea": "Stamford Bridge",
    "Newcastle": "St James' Park",
    "Club Brugge": "Jan Breydel Stadium",
    "Olympiakos": "Karaiskakis Stadium",
    "Frankfurt": "Deutsche Bank Park",
    "Slavia Praha": "Fortuna Arena",
    "København": "Parken Stadium",
}


def get_venue(home_team: str) -> str:
    """Get the stadium name for a match based on the home team."""
    return VENUE_MAP.get(home_team, "")
