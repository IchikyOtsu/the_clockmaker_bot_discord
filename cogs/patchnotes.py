from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

COLOR_PATCH = 0x5865F2   # Blurple Discord

# ---------------------------------------------------------------------------
# Patch notes — hardcoded versions
# ---------------------------------------------------------------------------

def _build_embed(version: str, title: str, sections: list[tuple[str, str]]) -> discord.Embed:
    embed = discord.Embed(
        title=f"📋  Patch Notes — {version}",
        description=f"**{title}**",
        color=COLOR_PATCH,
    )
    for name, value in sections:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text="The Clockmaster • /dev-patchnote")
    return embed


VERSIONS: dict[str, discord.Embed] = {
    "1.0.0": _build_embed(
        "v1.0.0", "Lancement",
        [
            ("👤  Personnages", (
                "`/chara-create` — Créer un personnage\n"
                "`/profil [@joueur]` — Consulter un profil\n"
                "`/chara-edit` — Modifier son personnage\n"
                "`/races-list` — Voir les races disponibles"
            )),
            ("🃏  Tirage & Défis", (
                "`/tirage` — Tirer une carte et recevoir un défi du jour\n"
                "`/mon-defi` — Consulter ou valider son défi en cours"
            )),
            ("💬  Confessions", (
                "`/confess` — Soumettre une confession anonyme\n"
                "`/reply <id>` — Répondre anonymement à une confession\n"
                "`/report <id>` — Signaler une confession\n"
                "`/supprimer <id>` — Supprimer sa propre confession"
            )),
            ("🌤️  Météo & Anniversaires", (
                "`/meteo` — Météo du jour\n"
                "`/config-meteo` — Configurer l'annonce météo automatique\n"
                "`/config-anniv` — Configurer les annonces d'anniversaires"
            )),
        ],
    ),
    "2.0.0": _build_embed(
        "v2.0.0", "Contenu & Modération",
        [
            ("🌤️  Météo par saisons", (
                "Chaque type de météo a maintenant des probabilités différentes selon la saison "
                "(printemps, été, automne, hiver)\n"
                "`/list-meteo` — Navigation par boutons saisonniers pour voir les probabilités\n"
                "`/add-meteo` — Poids séparés par saison (`printemps`, `ete`, `automne`, `hiver`)"
            )),
            ("💬  Confessions — Améliorations modération", (
                "Mode révision : chaque confession passe par le salon modération avant publication\n"
                "Bouton **Répondre** persistant sur les confessions publiées\n"
                "Les réponses passent aussi par le canal de modération si le mode révision est actif\n"
                "Boutons ⭐ **+Réputation** / 💀 **−Réputation** sur le salon modo après approbation\n"
                "Bouton ✖️ **Fermer** pour retirer les boutons de réputation manuellement\n"
                "`/banconfess` / `/debanconfess` — Bannir/débannir des confessions\n"
                "`/recours` — Faire un recours en cas de bannissement"
            )),
            ("🎂  Dates avant J.-C.", (
                "Les dates de naissance peuvent maintenant être négatives\n"
                "Format : `JJ/MM/-500` pour le 14 mars 500 av. J.-C.\n"
                "Affiché comme `14 mars 500 av. J.-C.` sur le profil"
            )),
        ],
    ),
    "3.0.0": _build_embed(
        "v3.0.0", "Système multi-personnages",
        [
            ("👤  Multi-personnages", (
                "Chaque joueur peut maintenant avoir **plusieurs personnages** sur un serveur\n"
                "La limite est configurable par les admins via `/config-perso max:<1–10>` (défaut : 2)\n"
                "`/chara-list [@joueur]` — Voir tous ses personnages (ou ceux d'un autre joueur)\n"
                "`/chara-switch` — Changer de personnage actif via dropdown (se supprime après)\n"
                "Le footer des messages indique le personnage actif concerné"
            )),
            ("✏️  Création & Édition", (
                "`/chara-create [avatar]` — Le faceclaim est maintenant optionnel\n"
                "Possibilité d'uploader une photo de profil **directement à la création** (pièce jointe)\n"
                "La liste déroulante des races se supprime automatiquement après la sélection\n"
                "`/chara-edit personnage:...` — Modifier **n'importe quel perso** (pas seulement l'actif)\n"
                "Autocomplete sur le champ personnage avec ✓ sur le perso actif"
            )),
            ("🃏  Tirage & Défis par personnage", (
                "`/tirage` demande maintenant quel personnage tire les cartes\n"
                "La limite **1 tirage / jour** est par personnage — chaque perso tire indépendamment\n"
                "`/mon-defi` demande aussi quel personnage pour afficher le défi correspondant\n"
                "Les listes déroulantes de sélection se suppriment après usage"
            )),
            ("🔧  Renommage des commandes", (
                "`/create characters` → `/chara-create`\n"
                "`/editchara` → `/chara-edit`\n"
                "`/switch` → `/chara-switch`\n"
                "`/races list` → `/races-list`"
            )),
        ],
    ),
}

VERSIONS_ORDER = ["3.0.0", "2.0.0", "1.0.0"]   # newest first


# ---------------------------------------------------------------------------
# View — dropdown pour naviguer entre les versions
# ---------------------------------------------------------------------------

class PatchnoteView(discord.ui.View):

    def __init__(self) -> None:
        super().__init__(timeout=120)
        self._message: discord.Message | None = None

        select = discord.ui.Select(
            placeholder="Voir une version précédente…",
            options=[
                discord.SelectOption(
                    label=f"v{v}",
                    value=v,
                    description=VERSIONS[v].description or "",
                    default=(v == VERSIONS_ORDER[0]),
                )
                for v in VERSIONS_ORDER
            ],
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        version = interaction.data["values"][0]
        await interaction.response.edit_message(embed=VERSIONS[version])

    async def on_timeout(self) -> None:
        if self._message:
            try:
                await self._message.edit(view=None)
            except discord.HTTPException:
                pass


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class PatchnotesCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="dev-patchnote",
        description="Consulter les notes de mise à jour du bot.",
    )
    async def dev_patchnote(self, interaction: discord.Interaction) -> None:
        view = PatchnoteView()
        await interaction.response.send_message(
            embed=VERSIONS[VERSIONS_ORDER[0]],
            view=view,
        )
        view._message = await interaction.original_response()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PatchnotesCog(bot))
