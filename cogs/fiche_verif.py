from __future__ import annotations

import re
from dataclasses import dataclass, field

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLOR_GREEN  = 0x57F287
COLOR_RED    = 0xED4245

_GDOC_ID_RE = re.compile(r"docs\.google\.com/document/d/([\w-]+)")

# Template placeholder strings that should NOT count as actual values
_PLACEHOLDER_RE = re.compile(
    r"^\s*\{[^}]*\}\s*$"
    r"|physique\s+et\s+r[eé]el"
    r"|facultatif"
    r"|amis\s*/\s*ennemis"
    r"|il est obligatoire",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class VerifResult:
    # IDENTITE
    nom: str = ""
    prenom: str = ""
    surnoms: str = ""
    avatar: str = ""
    genre_pronoms: str = ""
    date_naissance: str = ""
    age: str = ""
    orientation: str = ""
    nationalite: str = ""
    espece: str = ""
    relations: list[str] = field(default_factory=list)
    metier: str = ""
    description_physique: str = ""
    clan_meute: str = ""        # facultatif

    # PERSONNALITE
    section_personnalite: bool = False
    pers_content_len: int = 0   # longueur brute de la section pour fallback
    qualites: int = 0
    defauts: int = 0
    aime: int = 0
    naime_pas: int = 0
    peurs: int = 0

    # HISTOIRE
    section_histoire: bool = False
    histoire_len: int = 0

    # AUTORISATION
    section_autorisation: bool = False
    blessures_superficielles: bool = False
    blessures_graves: bool = False
    agressions_sexuelles: bool = False


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _clean_value(value: str) -> str:
    """Remove template placeholders in braces and strip."""
    value = re.sub(r"\{[^}]*\}", "", value).strip()
    return value


def _is_placeholder(value: str) -> bool:
    return bool(_PLACEHOLDER_RE.search(value))


def _extract_field(text: str, pattern: str) -> str:
    """Extract single-line value after 'Field :' pattern."""
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return ""
    value = _clean_value(m.group(1))
    if not value or _is_placeholder(value):
        return ""
    return value


def _section_text(full_text: str, start_pattern: str, end_pattern: str | None) -> str:
    """Extract text between two section headers (end_pattern=None → end of text)."""
    m = re.search(start_pattern, full_text, re.IGNORECASE)
    if not m:
        return ""
    start = m.end()
    if end_pattern:
        m2 = re.search(end_pattern, full_text[start:], re.IGNORECASE)
        if m2:
            return full_text[start : start + m2.start()]
    return full_text[start:]


def _count_items(text: str) -> int:
    """Count list items: bullet lines (-•*→) or comma-separated, skipping blanks."""
    text = text.strip()
    if not text:
        return 0
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # Filter out lines that look like section headers or instructions
    lines = [l for l in lines if not re.match(r"^[A-ZÉÀÈÊ\s]{4,}$", l)]
    bullet_lines = [l for l in lines if re.match(r"^[-•*→]\s+\S", l)]
    if bullet_lines:
        return len(bullet_lines)
    # Try comma-separated on first non-empty line
    for line in lines:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) >= 2:
            return len(parts)
    return len(lines)


def _extract_personality_block(pers_text: str, keyword: str, stop_keywords: list[str]) -> str:
    """Extract the content block following a personality keyword label."""
    pattern = rf"(?:^|\n)\s*{keyword}\s*[:\-]?\s*"
    m = re.search(pattern, pers_text, re.IGNORECASE)
    if not m:
        return ""
    start = m.end()
    remaining = pers_text[start:]
    # Cut at next keyword or major line break
    stop_pat = "|".join(
        rf"(?:^|\n)\s*{kw}\s*[:\-]" for kw in stop_keywords
    )
    if stop_pat:
        m2 = re.search(stop_pat, remaining, re.IGNORECASE)
        if m2:
            return remaining[: m2.start()]
    return remaining


# ---------------------------------------------------------------------------
# Parse & Verify
# ---------------------------------------------------------------------------

_S_IDENTITE     = r"IDENTIT[EÉ]"
_S_PERSONNALITE = r"PERSONNALITE|PERSONALIT[EÉ]|PERSONNALITÉ"
_S_HISTOIRE     = r"HISTOIRE"
_S_AUTORISATION = r"AUTORISATION"


def _parse_and_verify(text: str) -> VerifResult:
    result = VerifResult()

    # ------------------------------------------------------------------ #
    # IDENTITE
    # ------------------------------------------------------------------ #
    id_text = _section_text(text, _S_IDENTITE, f"{_S_PERSONNALITE}|{_S_HISTOIRE}|{_S_AUTORISATION}")
    src = id_text if id_text else text   # fallback to full doc

    result.nom           = _extract_field(src, r"Nom\s*:\s*(.+)")
    result.prenom        = _extract_field(src, r"Pr[eé]nom\s*:\s*(.+)")
    result.surnoms       = _extract_field(src, r"Surnoms?\s*:\s*(.+)")
    result.avatar        = _extract_field(src, r"Avatar\s*:\s*(.+)")
    result.genre_pronoms = _extract_field(src, r"Genre\s+et\s+pronoms?\s*:\s*(.+)")
    result.date_naissance= _extract_field(src, r"Date\s*[&et]+\s*Lieux?\s+de\s+naissance\s*:\s*(.+)")
    result.age           = _extract_field(src, r"\bAge\s*:\s*(.+)")
    result.orientation   = _extract_field(src, r"Orientation\s+sexuelle\s*:\s*(.+)")
    result.nationalite   = _extract_field(src, r"Nationalit[eé]\s*:\s*(.+)")
    result.espece        = _extract_field(src, r"Esp[eè]ce\s*:\s*(.+)")
    result.clan_meute    = _extract_field(src, r"Clan\s*/\s*Meute\s*:\s*(.+)")
    result.metier        = _extract_field(src, r"M[eé]tiers?\s*(?:\([sS]\))?\s*[/]\s*[EÉ]tudes?\s*(?:\([sS]\))?\s*:\s*(.+)")
    result.description_physique = _extract_field(src, r"Descriptions?\s+Physique[s]?\s*:\s*(.+)")

    # Relations: capture content block after the label, count non-template lines
    rel_m = re.search(
        r"Relations?\s*:\s*(.+?)(?=\n\s*\n|\n\s*M[eé]tier|\n\s*Descriptions?|\Z)",
        src, re.IGNORECASE | re.DOTALL,
    )
    if rel_m:
        rel_raw = _clean_value(rel_m.group(1))
        items = [
            l.strip() for l in re.split(r"[\n,]", rel_raw)
            if l.strip() and len(l.strip()) > 3 and not _is_placeholder(l)
        ]
        result.relations = items

    # ------------------------------------------------------------------ #
    # PERSONNALITE
    # ------------------------------------------------------------------ #
    pers_text = _section_text(text, _S_PERSONNALITE, f"{_S_HISTOIRE}|{_S_AUTORISATION}")
    if pers_text:
        result.section_personnalite = True
        clean_pers = _clean_value(pers_text)
        result.pers_content_len = len(clean_pers)

        # Qualités
        q_block = _extract_personality_block(
            pers_text, r"qualit[eé]s?",
            [r"d[eé]fauts?", r"aime[sz]?", r"peurs?"],
        )
        result.qualites = _count_items(q_block)

        # Défauts
        d_block = _extract_personality_block(
            pers_text, r"d[eé]fauts?",
            [r"aime[sz]?", r"peurs?", r"qualit[eé]s?"],
        )
        result.defauts = _count_items(d_block)

        # N'aime pas (must come before aime to avoid overlap)
        np_block = _extract_personality_block(
            pers_text, r"(?:n['\u2019]?|ne\s+)aime[sz]?\s+pas",
            [r"peurs?", r"qualit[eé]s?", r"d[eé]fauts?"],
        )
        result.naime_pas = _count_items(np_block)

        # Aime (positive) — exclude the n'aime pas match
        aime_text = re.sub(
            r"(?:n['\u2019]?|ne\s+)aime[sz]?\s+pas.+", "", pers_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        a_block = _extract_personality_block(
            aime_text, r"aime[sz]?",
            [r"d[eé]fauts?", r"peurs?", r"qualit[eé]s?"],
        )
        result.aime = _count_items(a_block)

        # Peurs
        p_block = _extract_personality_block(
            pers_text, r"peurs?",
            [r"qualit[eé]s?", r"d[eé]fauts?", r"aime[sz]?"],
        )
        result.peurs = _count_items(p_block)

    # ------------------------------------------------------------------ #
    # HISTOIRE
    # ------------------------------------------------------------------ #
    hist_text = _section_text(text, _S_HISTOIRE, _S_AUTORISATION)
    if hist_text:
        result.section_histoire = True
        clean_hist = re.sub(
            r"\(Un minimum est requis[^)]*\)", "", hist_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        result.histoire_len = len(clean_hist.strip())

    # ------------------------------------------------------------------ #
    # AUTORISATION DE BLESSURE
    # ------------------------------------------------------------------ #
    auth_text = _section_text(text, _S_AUTORISATION, None)
    if auth_text:
        result.section_autorisation = True
        result.blessures_superficielles = bool(
            re.search(r"Blessures?\s+superficiel\w*\s*:\s*(Oui|Non)", auth_text, re.IGNORECASE)
        )
        result.blessures_graves = bool(
            re.search(r"Blessures?\s+graves?\s*:\s*(Oui|Non)", auth_text, re.IGNORECASE)
        )
        result.agressions_sexuelles = bool(
            re.search(r"Agressions?\s+sexuelles?\s*:\s*(Oui|Non)", auth_text, re.IGNORECASE)
        )

    return result


# ---------------------------------------------------------------------------
# Report embed
# ---------------------------------------------------------------------------

def _ck(ok: bool) -> str:
    return "✅" if ok else "❌"


def _build_report_embed(result: VerifResult) -> discord.Embed:
    issues = 0

    # Count hard issues
    required_identity = [
        result.nom, result.prenom, result.avatar, result.genre_pronoms,
        result.date_naissance, result.age, result.orientation,
        result.nationalite, result.espece, result.metier,
        result.description_physique,
    ]
    for f in required_identity:
        if not f:
            issues += 1
    if not result.relations:
        issues += 1
    if not result.section_personnalite:
        issues += 1
    else:
        no_counts = all(
            c == 0 for c in [result.qualites, result.defauts, result.aime, result.naime_pas, result.peurs]
        )
        if no_counts and result.pers_content_len > 80:
            pass  # format non reconnu mais section présente — avertissement seulement, pas une erreur
        else:
            if result.qualites < 3:  issues += 1
            if result.defauts < 3:   issues += 1
            if result.aime < 3:      issues += 1
            if result.naime_pas < 3: issues += 1
            if result.peurs < 2:     issues += 1
    if not result.section_histoire:
        issues += 1
    elif result.histoire_len < 150:
        issues += 1
    if not result.section_autorisation:
        issues += 1
    else:
        if not result.blessures_superficielles: issues += 1
        if not result.blessures_graves:         issues += 1
        if not result.agressions_sexuelles:     issues += 1

    # Title
    name_parts = [x for x in [result.prenom, result.nom] if x]
    char_name = " ".join(name_parts) if name_parts else "Personnage inconnu"
    title = f"🔍  Rapport de vérification — {char_name}"

    embed = discord.Embed(title=title, color=COLOR_GREEN if issues == 0 else COLOR_RED)

    # ── IDENTITE ──
    id_lines = [
        f"{_ck(bool(result.nom))} Nom",
        f"{_ck(bool(result.prenom))} Prénom",
        f"{_ck(bool(result.surnoms))} Surnoms",
        f"{_ck(bool(result.avatar))} Avatar",
        f"{_ck(bool(result.genre_pronoms))} Genre et pronoms",
        f"{_ck(bool(result.date_naissance))} Date & Lieu de naissance",
        f"{_ck(bool(result.age))} Âge",
        f"{_ck(bool(result.orientation))} Orientation sexuelle",
        f"⬜ Clan/Meute *(facultatif)*",
        f"{_ck(bool(result.nationalite))} Nationalité",
        f"{_ck(bool(result.espece))} Espèce",
        f"{_ck(bool(result.relations))} Relations ({len(result.relations)} trouvée(s), min. 1)",
        f"{_ck(bool(result.metier))} Métier(s) / Étude(s)",
        f"{_ck(bool(result.description_physique))} Description Physique",
    ]
    embed.add_field(name="👤  Identité", value="\n".join(id_lines), inline=False)

    # ── PERSONNALITE ──
    if result.section_personnalite:
        # If counts are all 0 but section has content → likely undetectable format
        no_counts = all(
            c == 0 for c in [result.qualites, result.defauts, result.aime, result.naime_pas, result.peurs]
        )
        if no_counts and result.pers_content_len > 80:
            pers_lines = [
                "⚠️ Section présente mais format non reconnu — vérification manuelle requise",
                f"*(contenu détecté : {result.pers_content_len} caractères)*",
            ]
        else:
            def _ck_count(n: int, minimum: int) -> str:
                return "✅" if n >= minimum else ("⚠️" if n > 0 else "❌")
            pers_lines = [
                f"{_ck_count(result.qualites, 3)} Qualités ({result.qualites}/3)",
                f"{_ck_count(result.defauts, 3)} Défauts ({result.defauts}/3)",
                f"{_ck_count(result.aime, 3)} Aime ({result.aime}/3)",
                f"{_ck_count(result.naime_pas, 3)} N'aime pas ({result.naime_pas}/3)",
                f"{_ck_count(result.peurs, 2)} Peurs ({result.peurs}/2)",
            ]
    else:
        pers_lines = ["❌ Section introuvable"]
    embed.add_field(name="🎭  Personnalité", value="\n".join(pers_lines), inline=False)

    # ── HISTOIRE ──
    if result.section_histoire:
        hist_ok = result.histoire_len >= 150
        hist_lines = [f"{_ck(hist_ok)} Contenu ({result.histoire_len} caractères, min. 150)"]
    else:
        hist_lines = ["❌ Section introuvable"]
    embed.add_field(name="📖  Histoire", value="\n".join(hist_lines), inline=False)

    # ── AUTORISATION ──
    if result.section_autorisation:
        auth_lines = [
            f"{_ck(result.blessures_superficielles)} Blessures superficielles (Oui/Non)",
            f"{_ck(result.blessures_graves)} Blessures graves (Oui/Non)",
            f"{_ck(result.agressions_sexuelles)} Agressions sexuelles (Oui/Non)",
        ]
    else:
        auth_lines = ["❌ Section introuvable"]
    embed.add_field(name="⚔️  Autorisation de blessure", value="\n".join(auth_lines), inline=False)

    # ── Notes ──
    if issues == 0:
        summary = "✅ Aucun problème détecté — fiche conforme !"
    else:
        summary = f"❌ **{issues} problème(s) détecté(s)** à corriger avant validation."
    notes = (
        f"{summary}\n"
        "⚠️ Les images ne peuvent pas être vérifiées via export texte — à contrôler manuellement.\n"
        "⚠️ Le comptage personnalité peut être imprécis si le format s'éloigne du modèle."
    )
    embed.add_field(name="📝  Résumé", value=notes, inline=False)
    embed.set_footer(text="The Clockmaster • Vérification de fiche")

    return embed


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class FicheVerifCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _fetch_gdoc(self, url: str) -> str:
        m = _GDOC_ID_RE.search(url)
        if not m:
            raise ValueError("Ce n'est pas un lien Google Docs valide.")
        doc_id = m.group(1)
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        assert self._session is not None
        async with self._session.get(export_url, allow_redirects=True) as resp:
            if resp.status == 403:
                raise PermissionError(
                    "Le document est privé. Passe-le en accès **public (lecture seule)** avant de lancer la vérification."
                )
            if resp.status != 200:
                raise RuntimeError(f"Impossible d'accéder au document (HTTP {resp.status}).")
            return await resp.text(encoding="utf-8", errors="replace")

    @app_commands.command(
        name="verif-fiche",
        description="Vérifier une fiche RP en entrant son lien Google Docs public.",
    )
    @app_commands.describe(
        lien="Lien Google Docs de la fiche (doit être accessible publiquement en lecture)"
    )
    async def verif_fiche(self, interaction: discord.Interaction, lien: str) -> None:
        await interaction.response.defer()

        try:
            text = await self._fetch_gdoc(lien)
        except ValueError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        except PermissionError as exc:
            await interaction.followup.send(f"🔒 {exc}", ephemeral=True)
            return
        except RuntimeError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return

        result = _parse_and_verify(text)
        embed = _build_report_embed(result)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FicheVerifCog(bot))
