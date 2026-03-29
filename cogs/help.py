from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

COLOR_GOLD = 0xC9A84C


def _field(lines: list[tuple[str, str]]) -> str:
    return "\n".join(f"`{cmd}` — {desc}" for cmd, desc in lines)


# ---------------------------------------------------------------------------
# Embeds par catégorie
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, discord.Embed] = {}  # built lazily on first /help


def _build_embeds() -> dict[str, discord.Embed]:
    def embed(title: str, fields: list[tuple[str, list[tuple[str, str]]]]) -> discord.Embed:
        e = discord.Embed(title=title, color=COLOR_GOLD)
        for name, lines in fields:
            e.add_field(name=name, value=_field(lines), inline=False)
        e.set_footer(text="The Clockmaster")
        return e

    return {
        "personnage": embed("🧑‍🤝‍🧑  Personnage", [
            ("Commandes", [
                ("/chara-create",         "Créer ton personnage (avatar optionnel en pièce jointe)"),
                ("/chara-list [@joueur]",  "Voir la liste de tes personnages (ou ceux d'un autre joueur)"),
                ("/profil [nom]",          "Consulter le profil d'un personnage"),
                ("/chara-edit",            "Modifier ton personnage (nom, espèce, réputation, avatar…)"),
                ("/chara-switch",          "Changer de personnage actif"),
                ("/says <message>",        "Envoyer un message au nom de ton personnage actif (❌ pour supprimer)"),
                ("/metier-list",           "Voir tous les métiers disponibles et leurs titulaires"),
                ("/metier-prendre",        "Réserver un métier pour ton personnage actif"),
                ("/metier-quitter",        "Quitter ton métier actuel"),
            ]),
        ]),
        "tirage": embed("🃏  Tirage & Défis", [
            ("Commandes joueur", [
                ("/tirage",   "Tirer une carte (1×/jour par personnage) — choisir son perso"),
                ("/mon-defi", "Voir ton défi en cours (boutons : valider / fermer)"),
            ]),
        ]),
        "meteo": embed("🌤️  Météo", [
            ("Commandes", [
                ("/meteo",      "Météo du jour"),
                ("/list-meteo", "Voir tous les types de météo et leurs probabilités"),
            ]),
        ]),
        "races": embed("🗂️  Races", [
            ("Commandes", [
                ("/races-list", "Afficher toutes les races disponibles"),
            ]),
        ]),
        "confessions": embed("💬  Confessions", [
            ("Commandes joueur", [
                ("/confess",           "Soumettre une confession anonyme"),
                ("/reply <id>",        "Répondre anonymement à une confession"),
                ("/report <id>",       "Signaler une confession aux modérateurs"),
                ("/supprimer <id>",    "Supprimer ta propre confession"),
                ("/recours <raison>",  "Faire un recours si tu es banni des confessions"),
            ]),
        ]),
        "admin": embed("🔒  Administration", [
            ("Personnages", [
                ("/config-perso", "Définir le nombre max de personnages par joueur (1–10)"),
            ]),
            ("Météo & Anniversaires", [
                ("/config-meteo", "Configurer le salon et l'heure d'annonce météo"),
                ("/config-anniv", "Configurer le salon et l'heure des anniversaires"),
                ("/add-meteo",    "Ajouter un type de météo"),
                ("/del-meteo",    "Supprimer un type de météo"),
            ]),
            ("Races", [
                ("/races add",    "Ajouter une race jouable"),
                ("/races remove", "Désactiver une race"),
            ]),
            ("Types de cartes", [
                ("/card-type list",   "Lister les types de cartes"),
                ("/card-type add",    "Ajouter un type de carte"),
                ("/card-type edit",   "Modifier un type de carte"),
                ("/card-type remove", "Supprimer un type de carte"),
            ]),
            ("Cartes", [
                ("/card list",   "Lister toutes les cartes"),
                ("/card add",    "Ajouter une carte"),
                ("/card edit",   "Modifier une carte (nom, type, image)"),
                ("/card remove", "Désactiver une carte"),
            ]),
            ("Défis", [
                ("/defi list",   "Lister tous les défis"),
                ("/defi add",    "Ajouter un défi"),
                ("/defi edit",   "Modifier un défi"),
                ("/defi remove", "Désactiver un défi"),
                ("/defi link",   "Lier un défi à une carte"),
                ("/defi unlink", "Délier un défi d'une carte"),
            ]),
            ("Métiers", [
                ("/config-metier add",     "Ajouter un poste dans un établissement"),
                ("/config-metier remove",  "Désactiver un poste"),
                ("/config-metier limite",  "Modifier le nombre max de titulaires"),
                ("/config-metier retirer", "Forcer un personnage à quitter son poste"),
            ]),
            ("Tickets", [
                ("/ticket-setup",  "Créer un panel de tickets (wizard 5 étapes)"),
                ("/ticket-panels", "Lister les panels de tickets configurés"),
            ]),
            ("Confessions", [
                ("/confession setup",      "Configurer le salon et le mode révision"),
                ("/banconfess utilisateur", "Bannir un utilisateur des confessions"),
                ("/banconfess liste",       "Voir les utilisateurs bannis"),
                ("/banconfess nettoyer",    "Supprimer tous les bans de confessions"),
                ("/debanconfess utilisateur", "Débannir un utilisateur"),
                ("/debanconfess confession",  "Débannir l'auteur d'une confession (lien message)"),
            ]),
        ]),
    }


# ---------------------------------------------------------------------------
# Embed d'accueil (sélection de catégorie)
# ---------------------------------------------------------------------------

def _home_embed() -> discord.Embed:
    e = discord.Embed(
        title="The Clockmaster — Aide",
        description=(
            "Choisis une catégorie ci-dessous pour afficher les commandes correspondantes."
        ),
        color=COLOR_GOLD,
    )
    e.set_footer(text="The Clockmaster")
    return e


# ---------------------------------------------------------------------------
# View principale
# ---------------------------------------------------------------------------

# (key, label, style, row)
_CAT_BUTTONS = [
    ("personnage",  "🧑‍🤝‍🧑  Personnage",    discord.ButtonStyle.primary,   0),
    ("tirage",      "🃏  Tirage & Défis",  discord.ButtonStyle.primary,   0),
    ("meteo",       "🌤️  Météo",           discord.ButtonStyle.primary,   0),
    ("races",       "🗂️  Races",           discord.ButtonStyle.primary,   0),
    ("confessions", "💬  Confessions",     discord.ButtonStyle.primary,   0),
    ("admin",       "🔒  Administration",  discord.ButtonStyle.secondary, 1),
]


class HelpView(discord.ui.View):

    def __init__(self, embeds: dict[str, discord.Embed]) -> None:
        super().__init__(timeout=120)
        self._embeds = embeds
        self._add_cat_buttons(active=None)

    def _add_cat_buttons(self, active: str | None) -> None:
        self.clear_items()
        for key, label, style, row in _CAT_BUTTONS:
            btn = discord.ui.Button(
                label=label,
                style=style,
                custom_id=key,
                disabled=(key == active),
                row=row,
            )
            btn.callback = self._make_callback(key)
            self.add_item(btn)
        if active is not None:
            back = discord.ui.Button(
                label="⬅  Retour",
                style=discord.ButtonStyle.danger,
                custom_id="back",
                row=2,
            )
            back.callback = self._back_callback
            self.add_item(back)

    def _make_callback(self, key: str):
        async def callback(interaction: discord.Interaction) -> None:
            self._add_cat_buttons(active=key)
            await interaction.response.edit_message(embed=self._embeds[key], view=self)
        return callback

    async def _back_callback(self, interaction: discord.Interaction) -> None:
        self._add_cat_buttons(active=None)
        await interaction.response.edit_message(embed=_home_embed(), view=self)

    async def on_timeout(self) -> None:
        # Remove buttons but leave the message content unchanged
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        # We can't edit from on_timeout without storing the message reference,
        # so we store it on send and edit here.
        if hasattr(self, "_message") and self._message is not None:
            try:
                await self._message.edit(view=None)
            except discord.HTTPException:
                pass


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class HelpCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._embeds: dict[str, discord.Embed] = _build_embeds()

    @app_commands.command(name="help", description="Afficher la liste des commandes disponibles.")
    async def help(self, interaction: discord.Interaction) -> None:
        view = HelpView(self._embeds)
        await interaction.response.send_message(embed=_home_embed(), view=view, ephemeral=True)
        view._message = await interaction.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
