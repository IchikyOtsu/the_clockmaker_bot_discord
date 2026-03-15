from __future__ import annotations

import io
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, UnidentifiedImageError

from core.database import DatabaseClient, DatabaseError
from core.permissions import is_admin
from ui.embeds import error_embed, COLOR_DARK, COLOR_GREEN


def _to_jpeg(raw: bytes) -> bytes:
    """Convert any image to JPEG (512×512 max, aspect ratio preserved)."""
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except UnidentifiedImageError:
        raise ValueError("Le fichier ne semble pas être une image valide.")
    img.thumbnail((512, 512), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


class TirageAdminCog(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self) -> DatabaseClient:
        return self.bot.db  # type: ignore[attr-defined]

    # ==================================================================
    # GROUP /card-type
    # ==================================================================

    card_type_group = app_commands.Group(
        name="card-type",
        description="Gestion des types de cartes.",
    )

    @card_type_group.command(
        name="add", description="Ajouter un type de carte."
    )
    @app_commands.describe(
        nom="Nom du type (ex : Aventure, Combat, Mystère)",
        description="Description optionnelle du type",
    )
    async def card_type_add(
        self,
        interaction: discord.Interaction,
        nom: str,
        description: Optional[str] = None,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            ct = await self.db.add_card_type(str(interaction.guild_id), nom, description)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        embed = discord.Embed(
            title="Type de carte ajouté",
            description=f"**{ct.nom}**" + (f"\n{ct.description}" if ct.description else ""),
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_type_group.command(
        name="remove", description="Supprimer un type de carte."
    )
    @app_commands.describe(nom="Nom du type à supprimer")
    async def card_type_remove(
        self, interaction: discord.Interaction, nom: str
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            ct = await self.db.remove_card_type(str(interaction.guild_id), nom)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        embed = discord.Embed(
            title="Type de carte supprimé",
            description=f"**{ct.nom}** a été supprimé.",
            color=COLOR_DARK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_type_group.command(name="edit", description="Modifier un type de carte existant.")
    @app_commands.describe(
        id="ID court du type (visible dans /card-type list)",
        nom="Nouveau nom (optionnel)",
        description="Nouvelle description (optionnel)",
    )
    async def card_type_edit(
        self,
        interaction: discord.Interaction,
        id: str,
        nom: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        types = await self.db.get_card_types(guild_id)
        type_obj = next((t for t in types if str(t.id).startswith(id.strip())), None)
        if not type_obj:
            await interaction.followup.send(
                embed=error_embed(f"Type introuvable avec l'id « {id} »."), ephemeral=True
            )
            return

        updates: dict = {}
        if nom is not None:
            updates["nom"] = nom.strip()
        if description is not None:
            updates["description"] = description.strip()

        if not updates:
            await interaction.followup.send(
                embed=error_embed("Aucun champ à modifier fourni."), ephemeral=True
            )
            return

        try:
            type_obj = await self.db.update_card_type(str(type_obj.id), updates)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Type modifié",
            description=f"**{type_obj.nom}**" + (f"\n{type_obj.description}" if type_obj.description else ""),
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_type_edit.autocomplete("id")
    async def card_type_id_for_edit_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        types = await self.db.get_card_types(str(interaction.guild_id))
        return [
            app_commands.Choice(
                name=f"{str(t.id)[:8]} — {t.nom}",
                value=str(t.id)[:8],
            )
            for t in types
            if current.lower() in t.nom.lower() or str(t.id).startswith(current.lower())
        ][:25]

    @card_type_group.command(name="list", description="Lister tous les types de cartes.")
    async def card_type_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        types = await self.db.get_card_types(str(interaction.guild_id))
        if not types:
            await interaction.followup.send(
                embed=error_embed("Aucun type de carte enregistré."), ephemeral=True
            )
            return
        lines = []
        for t in types:
            short_id = str(t.id)[:8]
            line = f"`{short_id}` **{t.nom}**"
            if t.description:
                line += f" — {t.description}"
            lines.append(line)
        embed = discord.Embed(
            title=f"Types de cartes ({len(types)})",
            description="\n".join(lines),
            color=COLOR_DARK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_type_remove.autocomplete("nom")
    async def card_type_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        types = await self.db.get_card_types(str(interaction.guild_id))
        return [
            app_commands.Choice(name=t.nom, value=t.nom)
            for t in types
            if current.lower() in t.nom.lower()
        ][:25]

    # ==================================================================
    # GROUP /card
    # ==================================================================

    card_group = app_commands.Group(
        name="card",
        description="Gestion des cartes du tirage.",
    )

    @card_group.command(name="list", description="Lister toutes les cartes.")
    async def card_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        cards = await self.db.get_all_tirage_cards(str(interaction.guild_id))
        if not cards:
            await interaction.followup.send(
                embed=error_embed("Aucune carte enregistrée."), ephemeral=True
            )
            return
        active = [c for c in cards if c.is_active]
        inactive = [c for c in cards if not c.is_active]
        embed = discord.Embed(
            title=f"Cartes ({len(active)} actives, {len(inactive)} inactives)",
            color=COLOR_DARK,
        )
        if active:
            embed.add_field(
                name="✅  Actives",
                value="\n".join(f"`{str(c.id)[:8]}` **{c.nom}** — *{c.type_nom}*" for c in active) or "—",
                inline=False,
            )
        if inactive:
            embed.add_field(
                name="🚫  Inactives",
                value="\n".join(f"`{str(c.id)[:8]}` ~~{c.nom}~~ — *{c.type_nom}*" for c in inactive) or "—",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_group.command(name="add", description="Ajouter une carte.")
    @app_commands.describe(
        nom="Nom de la carte",
        type="Type de carte",
        image="Image de la carte (JPEG/PNG, optionnel)",
    )
    async def card_add(
        self,
        interaction: discord.Interaction,
        nom: str,
        type: str,
        image: Optional[discord.Attachment] = None,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return

        if image is not None and (
            not image.content_type or not image.content_type.startswith("image/")
        ):
            await interaction.response.send_message(
                embed=error_embed("Le fichier image doit être un JPEG ou PNG."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        # Resolve type name → type_id
        types = await self.db.get_card_types(guild_id)
        card_type = next((t for t in types if t.nom.lower() == type.lower()), None)
        if not card_type:
            await interaction.followup.send(
                embed=error_embed(f"Type introuvable : « {type} ». Utilise /card-type add d'abord."),
                ephemeral=True,
            )
            return

        try:
            card = await self.db.add_tirage_card(guild_id, nom, str(card_type.id))
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        # Upload image if provided
        image_url: Optional[str] = None
        if image is not None:
            try:
                raw = await image.read()
                jpeg_bytes = _to_jpeg(raw)
                image_url = await self.db.upload_card_image(guild_id, str(card.id), jpeg_bytes)
            except ValueError as exc:
                await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
                return
            except Exception as exc:
                import traceback
                traceback.print_exc()
                await interaction.followup.send(
                    embed=error_embed(f"Échec de l'upload : {exc}"),
                    ephemeral=True,
                )
                return

        embed = discord.Embed(
            title="Carte ajoutée",
            description=f"**{card.nom}** (type : {card.type_nom})",
            color=COLOR_GREEN,
        )
        if image_url:
            embed.set_thumbnail(url=image_url)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_group.command(name="remove", description="Désactiver une carte.")
    @app_commands.describe(nom="Nom de la carte à désactiver")
    async def card_remove(
        self, interaction: discord.Interaction, nom: str
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            card = await self.db.deactivate_tirage_card(str(interaction.guild_id), nom)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        embed = discord.Embed(
            title="Carte désactivée",
            description=f"**{card.nom}** n'apparaîtra plus dans les tirages.",
            color=COLOR_DARK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_group.command(name="edit", description="Modifier une carte existante.")
    @app_commands.describe(
        id="ID court de la carte (visible dans /card list)",
        nom="Nouveau nom (optionnel)",
        type="Nouveau type (optionnel)",
        image="Nouvelle image (optionnel)",
    )
    async def card_edit(
        self,
        interaction: discord.Interaction,
        id: str,
        nom: Optional[str] = None,
        type: Optional[str] = None,
        image: Optional[discord.Attachment] = None,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return

        if image is not None and (
            not image.content_type or not image.content_type.startswith("image/")
        ):
            await interaction.response.send_message(
                embed=error_embed("Le fichier image doit être un JPEG ou PNG."), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        # Find card by short or full ID
        cards = await self.db.get_all_tirage_cards(guild_id)
        card_obj = next((c for c in cards if str(c.id).startswith(id.strip())), None)
        if not card_obj:
            await interaction.followup.send(
                embed=error_embed(f"Carte introuvable avec l'id « {id} »."), ephemeral=True
            )
            return

        updates: dict = {}

        if nom is not None:
            updates["nom"] = nom.strip()

        if type is not None:
            types = await self.db.get_card_types(guild_id)
            card_type = next((t for t in types if t.nom.lower() == type.lower()), None)
            if not card_type:
                await interaction.followup.send(
                    embed=error_embed(f"Type introuvable : « {type} »."), ephemeral=True
                )
                return
            updates["type_id"] = str(card_type.id)

        if updates:
            try:
                card_obj = await self.db.update_tirage_card(str(card_obj.id), updates)
            except DatabaseError as exc:
                await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
                return

        if image is not None:
            try:
                raw = await image.read()
                jpeg_bytes = _to_jpeg(raw)
                await self.db.upload_card_image(guild_id, str(card_obj.id), jpeg_bytes)
            except ValueError as exc:
                await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
                return
            except Exception as exc:
                import traceback
                traceback.print_exc()
                await interaction.followup.send(
                    embed=error_embed(f"Échec de l'upload : {exc}"), ephemeral=True
                )
                return

        embed = discord.Embed(
            title="Carte modifiée",
            description=f"**{card_obj.nom}** (type : {card_obj.type_nom})",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @card_edit.autocomplete("id")
    async def card_id_for_edit_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cards = await self.db.get_all_tirage_cards(str(interaction.guild_id))
        return [
            app_commands.Choice(
                name=f"{str(c.id)[:8]} — {c.nom} ({c.type_nom})",
                value=str(c.id)[:8],
            )
            for c in cards
            if current.lower() in c.nom.lower() or str(c.id).startswith(current.lower())
        ][:25]

    @card_edit.autocomplete("type")
    async def card_type_for_edit_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        types = await self.db.get_card_types(str(interaction.guild_id))
        return [
            app_commands.Choice(name=t.nom, value=t.nom)
            for t in types if current.lower() in t.nom.lower()
        ][:25]

    @card_add.autocomplete("type")
    async def card_type_for_add_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        types = await self.db.get_card_types(str(interaction.guild_id))
        return [
            app_commands.Choice(name=t.nom, value=t.nom)
            for t in types if current.lower() in t.nom.lower()
        ][:25]

    @card_remove.autocomplete("nom")
    async def card_nom_for_remove_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cards = await self.db.get_all_tirage_cards(str(interaction.guild_id))
        return [
            app_commands.Choice(name=f"{c.nom} ({c.type_nom})", value=c.nom)
            for c in cards if c.is_active and current.lower() in c.nom.lower()
        ][:25]

    # ==================================================================
    # GROUP /defi
    # ==================================================================

    defi_group = app_commands.Group(
        name="defi",
        description="Gestion des défis.",
    )

    @defi_group.command(name="list", description="Lister tous les défis.")
    async def defi_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        defis = await self.db.get_all_defis(str(interaction.guild_id))
        if not defis:
            await interaction.followup.send(
                embed=error_embed("Aucun défi enregistré."), ephemeral=True
            )
            return
        active = [d for d in defis if d.is_active]
        inactive = [d for d in defis if not d.is_active]
        embed = discord.Embed(
            title=f"Défis ({len(active)} actifs, {len(inactive)} inactifs)",
            color=COLOR_DARK,
        )
        if active:
            lines = []
            for d in active:
                desc = d.description[:80] + "…" if len(d.description) > 80 else d.description
                lines.append(f"`{str(d.id)[:8]}` **{d.titre}** — {desc}")
            embed.add_field(name="✅  Actifs", value="\n".join(lines), inline=False)
        if inactive:
            embed.add_field(
                name="🚫  Inactifs",
                value="\n".join(f"`{str(d.id)[:8]}` ~~{d.titre}~~" for d in inactive),
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @defi_group.command(name="add", description="Ajouter un défi.")
    @app_commands.describe(
        titre="Titre du défi",
        description="Description détaillée du défi",
    )
    async def defi_add(
        self,
        interaction: discord.Interaction,
        titre: str,
        description: str,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            defi = await self.db.add_defi(str(interaction.guild_id), titre, description)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        embed = discord.Embed(
            title="Défi ajouté",
            description=f"**{defi.titre}**\n{defi.description}",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @defi_group.command(name="remove", description="Désactiver un défi.")
    @app_commands.describe(titre="Titre du défi à désactiver")
    async def defi_remove(
        self, interaction: discord.Interaction, titre: str
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            defi = await self.db.deactivate_defi(str(interaction.guild_id), titre)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return
        embed = discord.Embed(
            title="Défi désactivé",
            description=f"**{defi.titre}** n'apparaîtra plus dans les tirages.",
            color=COLOR_DARK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @defi_group.command(name="edit", description="Modifier un défi existant.")
    @app_commands.describe(
        id="ID court du défi (visible dans /defi list)",
        titre="Nouveau titre (optionnel)",
        description="Nouvelle description (optionnel)",
    )
    async def defi_edit(
        self,
        interaction: discord.Interaction,
        id: str,
        titre: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        defis = await self.db.get_all_defis(guild_id)
        defi_obj = next((d for d in defis if str(d.id).startswith(id.strip())), None)
        if not defi_obj:
            await interaction.followup.send(
                embed=error_embed(f"Défi introuvable avec l'id « {id} »."), ephemeral=True
            )
            return

        updates: dict = {}
        if titre is not None:
            updates["titre"] = titre.strip()
        if description is not None:
            updates["description"] = description.strip()

        if not updates:
            await interaction.followup.send(
                embed=error_embed("Aucun champ à modifier fourni."), ephemeral=True
            )
            return

        try:
            defi_obj = await self.db.update_defi(str(defi_obj.id), updates)
        except DatabaseError as exc:
            await interaction.followup.send(embed=error_embed(str(exc)), ephemeral=True)
            return

        embed = discord.Embed(
            title="Défi modifié",
            description=f"**{defi_obj.titre}**\n{defi_obj.description}",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @defi_edit.autocomplete("id")
    async def defi_id_for_edit_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        defis = await self.db.get_all_defis(str(interaction.guild_id))
        return [
            app_commands.Choice(
                name=f"{str(d.id)[:8]} — {d.titre}",
                value=str(d.id)[:8],
            )
            for d in defis
            if current.lower() in d.titre.lower() or str(d.id).startswith(current.lower())
        ][:25]

    @defi_group.command(name="link", description="Lier un défi à une carte.")
    @app_commands.describe(
        defi="Titre du défi",
        carte="Nom de la carte",
    )
    async def defi_link(
        self,
        interaction: discord.Interaction,
        defi: str,
        carte: str,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        defis = await self.db.get_all_defis(guild_id)
        defi_obj = next((d for d in defis if d.titre == defi and d.is_active), None)
        if not defi_obj:
            await interaction.followup.send(
                embed=error_embed(f"Défi actif introuvable : « {defi} »."), ephemeral=True
            )
            return

        cards = await self.db.get_active_tirage_cards(guild_id)
        card_obj = next((c for c in cards if c.nom == carte), None)
        if not card_obj:
            await interaction.followup.send(
                embed=error_embed(f"Carte active introuvable : « {carte} »."), ephemeral=True
            )
            return

        await self.db.link_card_defi(str(card_obj.id), str(defi_obj.id))
        embed = discord.Embed(
            title="Lien créé",
            description=f"**{carte}** est maintenant liée au défi **{defi}**.",
            color=COLOR_GREEN,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @defi_group.command(name="unlink", description="Délier un défi d'une carte.")
    @app_commands.describe(
        defi="Titre du défi",
        carte="Nom de la carte",
    )
    async def defi_unlink(
        self,
        interaction: discord.Interaction,
        defi: str,
        carte: str,
    ) -> None:
        if not await is_admin(interaction, self.db):
            await interaction.response.send_message(
                embed=error_embed("Commande réservée aux administrateurs."), ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        defis = await self.db.get_all_defis(guild_id)
        defi_obj = next((d for d in defis if d.titre == defi), None)
        if not defi_obj:
            await interaction.followup.send(
                embed=error_embed(f"Défi introuvable : « {defi} »."), ephemeral=True
            )
            return

        cards = await self.db.get_all_tirage_cards(guild_id)
        card_obj = next((c for c in cards if c.nom == carte), None)
        if not card_obj:
            await interaction.followup.send(
                embed=error_embed(f"Carte introuvable : « {carte} »."), ephemeral=True
            )
            return

        await self.db.unlink_card_defi(str(card_obj.id), str(defi_obj.id))
        embed = discord.Embed(
            title="Lien supprimé",
            description=f"**{carte}** n'est plus liée au défi **{defi}**.",
            color=COLOR_DARK,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # Autocomplete helpers for /defi commands
    @defi_remove.autocomplete("titre")
    @defi_link.autocomplete("defi")
    @defi_unlink.autocomplete("defi")
    async def defi_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        defis = await self.db.get_all_defis(str(interaction.guild_id))
        return [
            app_commands.Choice(name=d.titre, value=d.titre)
            for d in defis
            if d.is_active and current.lower() in d.titre.lower()
        ][:25]

    @defi_link.autocomplete("carte")
    @defi_unlink.autocomplete("carte")
    async def card_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cards = await self.db.get_all_tirage_cards(str(interaction.guild_id))
        return [
            app_commands.Choice(name=f"{c.nom} ({c.type_nom})", value=c.nom)
            for c in cards
            if c.is_active and current.lower() in c.nom.lower()
        ][:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TirageAdminCog(bot))
