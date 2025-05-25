"""
Gestionnaire Telegram multi-comptes ultra-sûr et interactif pour ajouter des membres entre groupes.

Fonctionnalités :
- Gestion multi-comptes Telegram (ajout, mise à jour, reconnexion, correction erreurs)
- Affichage état complet des comptes (connexions, erreurs, nombre d'ajouts)
- Choix interactif des groupes source et cible parmi tous les groupes accessibles
- Ajout des membres actifs récents (7 derniers jours)
- Rotation sécurisée entre comptes (10 membres max par compte, pauses longues aléatoires)
- Envoi du lien d'invitation si manque permission admin pour ajout direct
- Interface console intuitive avec menus numérotés pour toutes les actions

Prérequis :
- pip install telethon
- Créer tes comptes api_id/api_hash + numéros Telegram valides
- Respecter les limites Telegram pour éviter ban/flood
- Être membre (ou admin) des groupes source et cible

Usage :
- Lance ce script python
- Suis les instructions menu numéroté

"""

import asyncio
import random
import time
from datetime import datetime, timedelta
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetParticipantsRequest, InviteToChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusRecently, InputPeerEmpty

import sys

BASE_DELAY_BETWEEN_ADDS = 10
BASE_DELAY_BETWEEN_ACCOUNTS = 30
MEMBERS_PER_ACCOUNT = 10

# Listes globales
ACCOUNTS = []  # Structure dict {api_id, api_hash, phone, added_users, last_error, client}
GROUP_SOURCE = None
GROUP_TARGET = None
GROUP_INVITE_LINK = None  # Pour envoi si pas admin

def print_menu():
    print("\n=== MENU PRINCIPAL ===")
    print("1 - Ajouter / Mettre à jour un compte Telegram")
    print("2 - Afficher l'état des comptes")
    print("3 - Choisir groupes source et cible (parmi vos groupes)")
    print("4 - Mettre à jour / actualiser tous les comptes (connexion etc.)")
    print("5 - Lancer l'ajout des membres")
    print("6 - Quitter\n")

def input_account():
    print("\nSaisir les informations du compte Telegram :")
    try:
        api_id = int(input("api_id (numérique) : ").strip())
        api_hash = input("api_hash : ").strip()
        phone = input("Numéro de téléphone (+33...) : ").strip()
        return {'api_id': api_id, 'api_hash': api_hash, 'phone': phone, 'added_users': 0, 'last_error': None, 'client': None}
    except Exception as e:
        print(f"Entrée invalide : {e}")
        return None

def show_accounts():
    if not ACCOUNTS:
        print("Aucun compte configuré.")
        return
    print("\n--- ÉTAT DES COMPTES ---")
    for i, acc in enumerate(ACCOUNTS, 1):
        print(f"Compte #{i}")
        print(f"  Téléphone      : {acc['phone']}")
        print(f"  Ajouts membres : {acc.get('added_users', 0)}")
        print(f"  Dernière erreur: {acc.get('last_error', 'Aucune')}")
        print("")

async def connect_client(account):
    if account['client'] is not None and account['client'].is_connected():
        return account['client']
    client = TelegramClient(f'session_{account["phone"]}', account['api_id'], account['api_hash'])
    try:
        await client.start(phone=account['phone'])
        me = await client.get_me()
        print(f"[INFO] Connecté avec {me.first_name} ({account['phone']})")
        account['last_error'] = None
        account['client'] = client
        return client
    except errors.PhoneCodeInvalidError:
        print(f"[ERREUR] Code de confirmation invalide pour {account['phone']}.")
        account['last_error'] = "Code confirmation invalide"
    except errors.PhoneNumberBannedError:
        print(f"[ERREUR] Numéro banni : {account['phone']}")
        account['last_error'] = "Numéro banni"
    except Exception as e:
        print(f"[ERREUR] Erreur connexion {account['phone']}: {e}")
        account['last_error'] = str(e)
    return None

async def disconnect_client(account):
    if account['client'] is not None:
        try:
            await account['client'].disconnect()
            account['client'] = None
        except Exception:
            pass

def is_user_active_recently(user):
    from telethon.tl.types import UserStatusOnline, UserStatusOffline, UserStatusRecently
    status = getattr(user, 'status', None)
    if status is None:
        return False
    if isinstance(status, UserStatusRecently):
        return True
    if isinstance(status, UserStatusOnline):
        return True
    if isinstance(status, UserStatusOffline):
        if status.was_online is None:
            return False
        now = datetime.utcnow()
        delta_7_days = timedelta(days=7)
        if now - status.was_online <= delta_7_days:
            return True
    return False

async def get_all_groups(client):
    groups = []
    try:
        dialogs = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=100,
            hash=0
        ))
        for chat in dialogs.chats:
            # On prend les groupes (not channels privés, pas bots)
            if getattr(chat, 'megagroup', False):
                groups.append(chat)
    except Exception as e:
        print(f"[ERREUR] Récupération groupes : {e}")
    return groups

async def choose_group(account, purpose):
    client = await connect_client(account)
    if client is None:
        print(f"Impossible de se connecter avec {account['phone']}.")
        return None
    groups = await get_all_groups(client)
    if not groups:
        print("Aucun groupe trouvé.")
        return None
    print(f"\nChoisissez le groupe {purpose} parmi vos groupes (1-{len(groups)}) :")
    for i, g in enumerate(groups, 1):
        print(f"{i} - {g.title}")
    while True:
        choice = input(f"Numéro groupe {purpose} : ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(groups):
            chosen = groups[int(choice)-1]
            print(f"Group {purpose} sélectionné : {chosen.title}")
            await disconnect_client(account)
            return chosen
        print("Choix invalide. Réessayer.")

async def get_all_active_members(client, group):
    all_participants = []
    offset = 0
    limit = 100
    print(f"Récupération des membres actifs dans {group.title} ...")
    while True:
        participants = await client(GetParticipantsRequest(
            channel=group,
            filter=ChannelParticipantsSearch(''),
            offset=offset,
            limit=limit,
            hash=0
        ))
        if not participants.users:
            break
        filtered = [user for user in participants.users if is_user_active_recently(user)]
        all_participants.extend(filtered)
        offset += len(participants.users)
    print(f"Membres actifs récupérés: {len(all_participants)}")
    return all_participants

async def add_members(client, group_target, users_to_add, account):
    added_count = 0
    for user in users_to_add:
        try:
            await client(InviteToChannelRequest(
                channel=group_target,
                users=[user.id]
            ))
            print(f"[OK] Ajouté: {user.first_name} ({user.id}) avec {account['phone']}")
            added_count += 1
            account['added_users'] = account.get('added_users', 0) + 1
        except errors.UserPrivacyRestrictedError:
            print(f"[IGNORÉ] {user.first_name} empêche d'être ajouté (privacy).")
        except errors.UserAlreadyParticipantError:
            print(f"[IGNORÉ] {user.first_name} est déjà dans le groupe cible.")
        except errors.ChatAdminRequiredError:
            # Pas admin, on envoie lien invitation si défini
            if GROUP_INVITE_LINK:
                try:
                    invite_msg = f"Bonjour {user.first_name},\nJe vous invite à rejoindre ce groupe : {GROUP_INVITE_LINK}"
                    await client.send_message(user.id, invite_msg)
                    print(f"[INFO] Lien d'invitation envoyé à {user.first_name} ({user.id}) car pas admin.")
                    added_count +=1
                    account['added_users'] = account.get('added_users', 0) + 1
                except Exception as e:
                    print(f"[ERREUR] Impossible d’envoyer lien à {user.first_name} : {e}")
                    account['last_error'] = str(e)
            else:
                print(f"[ERREUR] Pas admin et pas de lien invitation défini, impossible d'ajouter {user.first_name}.")
        except errors.FloodWaitError as flood_err:
            print(f"[PAUSE] FloodWait {flood_err.seconds}s détecté sur {account['phone']}. Pause prolongée.")
            account['last_error'] = f"FloodWait {flood_err.seconds}s"
            await asyncio.sleep(flood_err.seconds + 10)
        except Exception as e:
            print(f"[ERREUR] Impossible d'ajouter {user.first_name} : {e}")
            account['last_error'] = str(e)

        delay = BASE_DELAY_BETWEEN_ADDS + random.uniform(-2, 2)
        await asyncio.sleep(max(5, delay))
    return added_count

async def run_addition():
    if not ACCOUNTS:
        print("Aucun compte configuré. Ajoute-en un via le menu.")
        return
    if not GROUP_SOURCE or not GROUP_TARGET:
        print("Groupes source et/ou cible non configurés. Configure-les via le menu.")
        return

    # Connection temporaire avec premier compte pour récupérer membres
    temp_client = await connect_client(ACCOUNTS[0])
    if temp_client is None:
        print("[ERREUR] Impossible de connecter le premier compte pour récupérer les membres.")
        return

    source_entity = GROUP_SOURCE
    target_entity = GROUP_TARGET

    members = await get_all_active_members(temp_client, source_entity)
    await temp_client.disconnect()

    if not members:
        print("Pas de membres actifs trouvés au groupe source.")
        return

    total_members = len(members)
    index = 0
    accounts_order = ACCOUNTS.copy()
    random.shuffle(accounts_order)

    while index < total_members:
        for account in accounts_order:
            if index >= total_members:
                break
            client = await connect_client(account)
            if client is None:
                print(f"Compte {account['phone']} inutilisable, passe au suivant.")
                continue

            users_batch = members[index:index + MEMBERS_PER_ACCOUNT]
            print(f"Ajout du batch {index // MEMBERS_PER_ACCOUNT + 1} de {len(users_batch)} membres avec {account['phone']}")
            added = await add_members(client, target_entity, users_batch, account)
            print(f"Ajoutés {added} membres avec {account['phone']}")
            await disconnect_client(account)

            delay_account = BASE_DELAY_BETWEEN_ACCOUNTS + random.uniform(-5, 5)
            print(f"Pause de {int(delay_account)} secondes avant changement de compte...")
            time.sleep(delay_account)

            index += MEMBERS_PER_ACCOUNT
            if index >= total_members:
                break

    print("Ajout terminé de tous les membres actifs.")

async def refresh_all_accounts():
    print("\nMise à jour et reconnexion de tous les comptes...")
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            print(f"{account['phone']} connecté avec succès.")
            account['last_error'] = None
            await disconnect_client(account)
        else:
            print(f"Échec de connexion pour {account['phone']}.")

def main_loop():
    global GROUP_SOURCE, GROUP_TARGET, GROUP_INVITE_LINK

    print("=== Gestionnaire Telegram multi-comptes ultra-sûr ===")
    while True:
        print_menu()
        choice = input("Choix (numéro) : ").strip()

        if choice == '1':
            acc = input_account()
            if acc:
                existing = next((a for a in ACCOUNTS if a['phone'] == acc['phone']), None)
                if existing:
                    print(f"Compte {acc['phone']} mis à jour.")
                    existing.update(acc)
                else:
                    ACCOUNTS.append(acc)
                    print(f"Compte {acc['phone']} ajouté.")

        elif choice == '2':
            show_accounts()

        elif choice == '3':
            if not ACCOUNTS:
                print("Aucun compte configuré pour récupérer les groupes.")
                continue
            # Choisir un compte pour liste groupes source et cible
            account = ACCOUNTS[0]  # On choisit le premier, ou on pourrait demander de choisir
            client_loop = asyncio.get_event_loop()
            groups = client_loop.run_until_complete(get_all_groups(client_loop.run_until_complete(connect_client(account))))
            if not groups:
                print("Aucun groupe disponible.")
                continue

            print("\nListe des groupes disponibles :")
            for i, g in enumerate(groups, 1):
                print(f"{i} - {g.title}")

            def select_group(msg):
                while True:
                    choice_g = input(msg).strip()
                    if choice_g.isdigit() and 1 <= int(choice_g) <= len(groups):
                        return groups[int(choice_g)-1]
                    print("Choix invalide.")

            GROUP_SOURCE = select_group("Numéro groupe source : ")
            GROUP_TARGET = select_group("Numéro groupe cible : ")

            GROUP_INVITE_LINK = input("Lien d'invitation du groupe cible (laisser vide si admin direct) : ").strip()
            print(f"Groupes configurés :\n - Source : {GROUP_SOURCE.title}\n - Cible : {GROUP_TARGET.title}")
            if GROUP_INVITE_LINK:
                print(f"Lien d'invitation défini pour la cible.")

        elif choice == '4':
            client_loop = asyncio.get_event_loop()
            client_loop.run_until_complete(refresh_all_accounts())

        elif choice == '5':
            client_loop = asyncio.get_event_loop()
            client_loop.run_until_complete(run_addition())

        elif choice == '6':
            print("Fin du programme. Au revoir !")
            sys.exit(0)

        else:
            print("Choix invalide. Réessaye.")


if __name__ == '__main__':
    main_loop()

