"""
Gestionnaire Telegram multi-comptes ultra-sûr, optimisé et robuste avec interface colorée.

Fonctionnalités principales complètes et optimisées :  
- Correction complète datetime UTC pour éviter erreurs  
- Interface console colorée ANSI, effacement écran entre menus  
- Gestion multi-comptes, vérification et reconnexion automatique  
- Choix interactif des groupes et canaux source et cible parmi tous accessibles  
- Ajout des membres actifs récents (7 derniers jours)  
- Rotation sécurisée avec pauses aléatoires optimales pour ratio efficacité / anti-ban  
- Envoi de lien d'invitation si absence de droits admin pour ajout direct  
- Gestion complète et reprise des erreurs courantes, FloodWait, privacy, limitations  
- Enregistrement local automatique des sessions Telethon pour réutilisation  
- Caches simples des membres récupérés pour éviter appels redondants  
- Menu clair et simple avec instructions et validations  
- Compatible Python 3.7+ et dernières versions Telethon

Nouveaux menus et fonctions :
- Gestion complète comptes  
- Récupérations, Ajouts/Messages (groupes & canaux)  
- Retirer/Rejoindre/Quitter groupes & canaux  
- Vues/Reactions/Sondage  
- Menu FEU (API creation & signalements)  
- Autres (actualisation script, etc.)
"""

# === IMPORTATIONS ===
import asyncio
import random
import time
import os
import sys
import json
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetParticipantsRequest, InviteToChannelRequest, JoinChannelRequest, LeaveChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest, GetFullChatRequest, GetHistoryRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusRecently, UserStatusOffline, UserStatusOnline, InputPeerEmpty, InputChannel
from telethon.utils import get_input_peer

# === CONSTANTES COULEURS ANSI ===
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    YELLOW = '\033[93m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# === PARAMÈTRES CONSTANTS ===
BASE_DELAY_BETWEEN_ADDS = 12
BASE_DELAY_BETWEEN_ACCOUNTS = 45
MEMBERS_PER_ACCOUNT = 8
MEMBER_CACHE_TTL = 3600  # 1 heure cache membres

SESSION_DIR = './sessions'
if not os.path.isdir(SESSION_DIR):
    os.mkdir(SESSION_DIR)

ACCOUNTS_FILE = 'accounts.json'

# === VARIABLES GLOBALES ===
ACCOUNTS = []
GROUP_SOURCE = None
GROUP_TARGET = None
GROUP_INVITE_LINK = None
MESSAGE_TO_SEND = None

MEMBERS_CACHE = {'timestamp': 0, 'members': []}

# === UTILITAIRES ===
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def save_accounts():
    try:
        data = [{
            'api_id': acc['api_id'],
            'api_hash': acc['api_hash'],
            'phone': acc['phone'],
            'added_users': acc.get('added_users', 0)
        } for acc in ACCOUNTS]
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"{Colors.WARNING}[WARN]{Colors.ENDC} Impossible de sauvegarder comptes: {e}")

def load_accounts():
    global ACCOUNTS
    try:
        if os.path.isfile(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r') as f:
                loaded = json.load(f)
                ACCOUNTS = []
                for acc in loaded:
                    ACCOUNTS.append({
                        'api_id': acc['api_id'],
                        'api_hash': acc['api_hash'],
                        'phone': acc['phone'],
                        'added_users': acc.get('added_users', 0),
                        'last_error': None,
                        'client': None
                    })
    except Exception as e:
        print(f"{Colors.WARNING}[WARN]{Colors.ENDC} Impossible de charger comptes: {e}")

# === GESTION DES COMPTES ===
def input_account():
    clear_screen()
    print(f"{Colors.BOLD}Saisir les informations du compte Telegram :{Colors.ENDC}")
    try:
        api_id = int(input('api_id (numérique) : ').strip())
        api_hash = input('api_hash : ').strip()
        phone = input('Numéro de téléphone (+33...) : ').strip()
        return {'api_id': api_id, 'api_hash': api_hash, 'phone': phone,
                'added_users': 0, 'last_error': None, 'client': None}
    except Exception as e:
        print(f"{Colors.FAIL}Entrée invalide : {e}{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return None

def show_accounts():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.UNDERLINE}--- ÉTAT DES COMPTES ---{Colors.ENDC}\n")
    if not ACCOUNTS:
        print(f"{Colors.WARNING}Aucun compte configuré.{Colors.ENDC}\n")
    else:
        for i, acc in enumerate(ACCOUNTS, 1):
            print(f"{Colors.OKBLUE}Compte #{i}{Colors.ENDC}")
            print(f"  Téléphone      : {Colors.OKGREEN}{acc['phone']}{Colors.ENDC}")
            print(f"  Ajouts membres : {Colors.OKGREEN}{acc.get('added_users', 0)}{Colors.ENDC}")
            err = acc.get('last_error')
            if err:
                print(f"  Dernière erreur: {Colors.FAIL}{err}{Colors.ENDC}")
            else:
                print(f"  Dernière erreur: {Colors.OKGREEN}Aucune{Colors.ENDC}")
            print('')
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def connect_client(account):
    if account['client'] is not None and account['client'].is_connected():
        return account['client']
    try:
        session_file = f"{SESSION_DIR}/session_{account['phone']}"
        client = TelegramClient(session_file, account['api_id'], account['api_hash'])
        await client.start(phone=account['phone'])
        me = await client.get_me()
        print(f"{Colors.OKGREEN}[INFO]{Colors.ENDC} Connecté avec {me.first_name} ({account['phone']})")
        account['client'] = client
        account['last_error'] = None
        return client
    except errors.PhoneCodeInvalidError:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Code confirmation invalide pour {account['phone']}")
        account['last_error'] = "Code confirmation invalide"
    except errors.PhoneNumberBannedError:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Numéro banni: {account['phone']}")
        account['last_error'] = "Numéro banni"
    except Exception as e:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Erreur connexion {account['phone']}: {e}")
        account['last_error'] = str(e)
    return None

async def disconnect_client(account):
    if account.get('client'):
        try:
            await account['client'].disconnect()
            account['client'] = None
        except:
            pass

def remove_account():
    clear_screen()
    print(f"{Colors.BOLD}Retirer un compte Telegram :{Colors.ENDC}")
    if not ACCOUNTS:
        print(f"{Colors.WARNING}Aucun compte configuré.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return
    for i, acc in enumerate(ACCOUNTS, 1):
        print(f"{Colors.OKBLUE}Compte #{i}{Colors.ENDC}: {acc['phone']}")
    choice = input("\nChoisissez le numéro du compte à retirer : ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(ACCOUNTS):
        removed = ACCOUNTS.pop(int(choice) - 1)
        print(f"{Colors.OKGREEN}Compte {removed['phone']} retiré.{Colors.ENDC}")
        save_accounts()
    else:
        print(f"{Colors.FAIL}Choix invalide.{Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")

# === UTILITAIRES MEMBRES ET GROUPES/CANAUX ===
def is_user_active_recently(user, inactive_days=7):
    status = getattr(user, 'status', None)
    if status is None:
        return False
    if isinstance(status, UserStatusRecently) or isinstance(status, UserStatusOnline):
        return True
    if isinstance(status, UserStatusOffline):
        if status.was_online is None:
            return False
        now = datetime.now(timezone.utc)
        delta = timedelta(days=inactive_days)
        was_online = status.was_online
        if was_online.tzinfo is None:
            was_online = was_online.replace(tzinfo=timezone.utc)
        return (now - was_online) <= delta
    return False

async def get_all_groups_channels(client):
    groups_channels = []
    try:
        dialogs = await client(GetDialogsRequest(offset_date=None, offset_id=0,
                offset_peer=InputPeerEmpty(), limit=300, hash=0))
        for chat in dialogs.chats:
            if getattr(chat, 'megagroup', False) or getattr(chat, 'broadcast', False):
                groups_channels.append(chat)
    except Exception as e:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Récupération groupes/canaux : {e}")
    return groups_channels

async def choose_group_channel(account, purpose):
    client = await connect_client(account)
    if not client:
        input(f"{Colors.FAIL}Impossible de se connecter avec {account['phone']}. Appuyez sur Entrée...{Colors.ENDC}")
        return None
    groups_channels = await get_all_groups_channels(client)
    if not groups_channels:
        input(f"{Colors.WARNING}Aucun groupe/canal trouvé. Appuyez sur Entrée...{Colors.ENDC}")
        await disconnect_client(account)
        return None
    while True:
        clear_screen()
        print(f"{Colors.BOLD}{Colors.UNDERLINE}Choisissez le groupe/canal {purpose} parmi vos groupes/canaux :{Colors.ENDC}")
        for i, g in enumerate(groups_channels, 1):
            g_type = 'Canal' if getattr(g, 'broadcast', False) else 'Groupe'
            print(f"{Colors.OKCYAN}{i}{Colors.ENDC} - [{g_type}] {g.title}")
        choice = input(f"\nNuméro groupe/canal {purpose} : ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(groups_channels):
            chosen = groups_channels[int(choice)-1]
            await disconnect_client(account)
            print(f"{Colors.OKGREEN}Groupe/canal {purpose} sélectionné : {chosen.title}{Colors.ENDC}")
            input(f"\n{Colors.WARNING}Appuyez sur Entrée pour continuer...{Colors.ENDC}")
            return chosen
        print(f"{Colors.FAIL}Choix invalide. Réessayez.{Colors.ENDC}")
        time.sleep(1)

async def get_active_members_from_channel(client, channel, days=7, limit_msgs=1000):
    active_users = {}
    now = datetime.now(timezone.utc)
    oldest_date = now - timedelta(days=days)
    offset_id = 0
    total_count = 0

    print(f"{Colors.OKBLUE}Récupération des membres actifs via messages dans le canal {channel.title} ...{Colors.ENDC}")

    while True:
        history = await client(GetHistoryRequest(
            peer=channel,
            offset_id=offset_id,
            offset_date=None,
            add_offset=0,
            limit=100,
            max_id=0,
            min_id=0,
            hash=0
        ))
        if not history.messages:
            break

        for message in history.messages:
            total_count += 1
            if message.date < oldest_date:
                break
            sender = await message.get_sender()
            if sender and sender.id not in active_users:
                if is_user_active_recently(sender, inactive_days=days):
                    active_users[sender.id] = sender

        if total_count >= limit_msgs or message.date < oldest_date:
            break

        offset_id = history.messages[-1].id

    print(f"{Colors.OKGREEN}Membres actifs détectés dans canal : {len(active_users)}{Colors.ENDC}")
    return list(active_users.values())

async def get_all_active_members(client, group_channel):
    global MEMBERS_CACHE
    now_ts = time.time()
    if MEMBERS_CACHE["timestamp"] + MEMBER_CACHE_TTL > now_ts and MEMBERS_CACHE["members"]:
        print(f"{Colors.OKBLUE}Utilisation du cache membres moins de {MEMBER_CACHE_TTL//60} minutes.{Colors.ENDC}")
        return MEMBERS_CACHE["members"]

    all_users = []

    if getattr(group_channel, 'megagroup', False):
        print(f"{Colors.OKBLUE}Récupération des membres actifs dans le groupe {group_channel.title} ...{Colors.ENDC}")
        offset = 0
        limit = 100
        try:
            while True:
                participants = await client(GetParticipantsRequest(
                    channel=group_channel,
                    filter=ChannelParticipantsSearch(''),
                    offset=offset,
                    limit=limit,
                    hash=0))
                if not participants.users:
                    break
                filtered = [user for user in participants.users if is_user_active_recently(user)]
                all_users.extend(filtered)
                offset += len(participants.users)
        except Exception as e:
            print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Récupération membres: {e}")
            return None

    elif getattr(group_channel, 'broadcast', False):
        all_users = await get_active_members_from_channel(client, group_channel)
    else:
        print(f"{Colors.WARNING}Type de groupe/canal inconnu pour récupération membres.{Colors.ENDC}")
        return None

    MEMBERS_CACHE["timestamp"] = now_ts
    MEMBERS_CACHE["members"] = all_users
    print(f"{Colors.OKGREEN}Membres actifs récupérés : {len(all_users)}{Colors.ENDC}")
    return all_users

async def add_members(client, group_target, users_to_add, account):
    added_count = 0
    for user in users_to_add:
        try:
            await client(InviteToChannelRequest(channel=group_target, users=[user.id]))
            added_count += 1
            account['added_users'] = account.get('added_users', 0) + 1
            print(f"{Colors.OKGREEN}[OK]{Colors.ENDC} Ajouté: {user.first_name or 'N/A'} ({user.id}) avec {account['phone']}")
        except errors.UserPrivacyRestrictedError:
            print(f"{Colors.WARNING}[IGNORÉ]{Colors.ENDC} {user.first_name or 'N/A'} empêche d'être ajouté (privacy).")
        except errors.UserAlreadyParticipantError:
            print(f"{Colors.WARNING}[IGNORÉ]{Colors.ENDC} {user.first_name or 'N/A'} est déjà dans le groupe/canal cible.")
        except errors.ChatAdminRequiredError:
            if GROUP_INVITE_LINK:
                try:
                    invite_msg = f"Bonjour {user.first_name or ''},\nJe vous invite à rejoindre ce groupe/canal : {GROUP_INVITE_LINK}"
                    await client.send_message(user.id, invite_msg)
                    added_count += 1
                    print(f"{Colors.OKCYAN}[INFO]{Colors.ENDC} Lien envoyé à {user.first_name or 'N/A'} ({user.id}) (pas admin).")
                except Exception as e:
                    print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Impossible d’envoyer lien à {user.first_name or 'N/A'}: {e}")
                    account['last_error'] = str(e)
            else:
                print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Pas de lien invitation défini, impossible d'ajouter {user.first_name or 'N/A'}.")
        except errors.FloodWaitError as flood_err:
            print(f"{Colors.WARNING}[PAUSE]{Colors.ENDC} FloodWait {flood_err.seconds}s sur {account['phone']}. Pause prolongée.")
            account['last_error'] = f"FloodWait {flood_err.seconds}s"
            await asyncio.sleep(flood_err.seconds + 10)
        except Exception as e:
            print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Impossible d'ajouter {user.first_name or 'N/A'} : {e}")
            account['last_error'] = str(e)
        await asyncio.sleep(BASE_DELAY_BETWEEN_ADDS + random.uniform(-3, 3))
    return added_count

async def run_addition():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.HEADER}Début ajout multi-compte membres actifs...{Colors.ENDC}\n")
    if not ACCOUNTS:
        print(f"{Colors.FAIL}Aucun compte configuré. Ajoute-en un via le menu.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return
    if GROUP_TARGET is None:
        print(f"{Colors.FAIL}Groupe/canal cible non configuré. Configure-le via le menu.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return
    if GROUP_SOURCE is None:
        print(f"{Colors.FAIL}Groupe/canal source non configuré. Configure-le via le menu.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return
    if not (getattr(GROUP_SOURCE, 'megagroup', False) or getattr(GROUP_SOURCE, 'broadcast', False)):
        print(f"{Colors.FAIL}Le groupe/canal source doit être un groupe (méga-groupe) ou un canal valide.{Colors.ENDC}")
        input(f"{Colors.WARNING}Veuillez choisir un groupe/canal source valide. Appuyez sur Entrée...{Colors.ENDC}")
        return
    temp_client = await connect_client(ACCOUNTS[0])
    if temp_client is None:
        print(f"{Colors.FAIL}Impossible de connecter le premier compte.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return
    members = await get_all_active_members(temp_client, GROUP_SOURCE)
    if members is None:
        print(f"{Colors.FAIL}Impossible de récupérer les membres actifs du groupe/canal source.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        await temp_client.disconnect()
        return
    await temp_client.disconnect()
    if not members:
        print(f"{Colors.WARNING}Pas de membres actifs trouvés au groupe/canal source.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
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
                print(f"{Colors.FAIL}Compte {account['phone']} inutilisable, passe au suivant.{Colors.ENDC}")
                continue
            users_batch = members[index:index + MEMBERS_PER_ACCOUNT]
            print(f"\n{Colors.OKBLUE}Ajout batch {index // MEMBERS_PER_ACCOUNT + 1} ({len(users_batch)}) avec {account['phone']}{Colors.ENDC}")
            added = await add_members(client, GROUP_TARGET, users_batch, account)
            print(f"{Colors.OKGREEN}Ajouté(s) {added} membre(s) avec {account['phone']}{Colors.ENDC}")
            await disconnect_client(account)
            delay = BASE_DELAY_BETWEEN_ACCOUNTS + random.uniform(-7, 7)
            print(f"{Colors.WARNING}Pause {int(delay)}s avant changement de compte...{Colors.ENDC}")
            time.sleep(delay)
            index += MEMBERS_PER_ACCOUNT
            if index >= total_members:
                break
    print(f"{Colors.OKGREEN}{Colors.BOLD}Ajout terminé.{Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def mass_message():
    clear_screen()
    print(f"{Colors.BOLD}Envoi de masse de messages :{Colors.ENDC}")
    if GROUP_SOURCE is None:
        print(f"{Colors.FAIL}Le groupe/canal source n'est pas configuré. Configurez-le via le menu (option 5).{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return
    message = input("Entrez le message à envoyer : ").strip()
    if not message:
        print(f"{Colors.FAIL}Message vide. Annulation.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            try:
                all_members = []
                offset = 0
                limit = 100
                while True:
                    participants = await client(GetParticipantsRequest(
                        channel=GROUP_SOURCE,
                        filter=ChannelParticipantsSearch(''),
                        offset=offset,
                        limit=limit,
                        hash=0
                    ))
                    if not participants.users:
                        break
                    all_members.extend(participants.users)
                    offset += len(participants.users)

                for m in all_members:
                    try:
                        await client.send_message(m.id, message)
                        print(f"{Colors.OKGREEN}Message envoyé à {m.first_name or 'N/A'} ({m.id}){Colors.ENDC}")
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"{Colors.FAIL}Erreur envoi message à {m.first_name or 'N/A'} ({m.id}): {e}{Colors.ENDC}")
            except Exception as e:
                print(f"{Colors.FAIL}Erreur lors de l'envoi de masse : {e}{Colors.ENDC}")
            await disconnect_client(account)
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def refresh_all_accounts():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.HEADER}Mise à jour et reconnexion de tous les comptes...{Colors.ENDC}\n")
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            print(f"{Colors.OKGREEN}{account['phone']} connecté.{Colors.ENDC}")
            account['last_error'] = None
            await disconnect_client(account)
        else:
            print(f"{Colors.FAIL}Échec connexion pour {account['phone']}.{Colors.ENDC}")
    save_accounts()
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def remove_inactive_members():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.HEADER}Retrait des membres inactifs (> 60 jours)...{Colors.ENDC}\n")
    if not ACCOUNTS:
        print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return
    if GROUP_SOURCE is None:
        print(f"{Colors.FAIL}Groupe/canal source non configuré. Configure-le via le menu.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    account = ACCOUNTS[0]
    client = await connect_client(account)
    if client is None:
        print(f"{Colors.FAIL}Impossible de connecter le compte {account['phone']}.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    inactive_threshold_days = 60
    inactive_members = []

    print(f"{Colors.OKBLUE}Récupération des membres du groupe/canal {GROUP_SOURCE.title}...{Colors.ENDC}")
    offset = 0
    limit = 100

    try:
        while True:
            participants = await client(GetParticipantsRequest(
                channel=GROUP_SOURCE,
                filter=ChannelParticipantsSearch(''),
                offset=offset,
                limit=limit,
                hash=0))
            if not participants.users:
                break
            for user in participants.users:
                status = getattr(user, 'status', None)
                # Considérer inactif si hors ligne > 60 jours
                if isinstance(status, UserStatusOffline):
                    was_online = status.was_online
                    if was_online is None:
                        inactive_members.append(user)
                    else:
                        now = datetime.now(timezone.utc)
                        if was_online.tzinfo is None:
                            was_online = was_online.replace(tzinfo=timezone.utc)
                        if (now - was_online).days > inactive_threshold_days:
                            inactive_members.append(user)
                elif status is None:
                    # Pas de status, on peut considérer inactif
                    inactive_members.append(user)
            offset += len(participants.users)
    except Exception as e:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Récupération membres: {e}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    print(f"{Colors.WARNING}Nombre de membres inactifs détectés (> {inactive_threshold_days} jours): {len(inactive_members)}{Colors.ENDC}")
    confirm = input(f"{Colors.FAIL}Voulez-vous retirer tous ces membres inactifs ? (o/N) : {Colors.ENDC}").strip().lower()
    if confirm != 'o':
        print("Annulation du retrait.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    removed_count = 0
    for user in inactive_members:
        try:
            # Retirer le membre du groupe/canal
            await client(LeaveChannelRequest(user.id))
            removed_count += 1
            print(f"{Colors.OKGREEN}Membre {user.first_name or 'N/A'} retiré.{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Impossible de retirer {user.first_name or 'N/A'} : {e}")
        await asyncio.sleep(BASE_DELAY_BETWEEN_ADDS + random.uniform(-3, 3))

    print(f"{Colors.OKGREEN}{removed_count} membres inactifs retirés avec succès.{Colors.ENDC}")
    await disconnect_client(account)
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def advanced_search_group_channel(account):
    clear_screen()
    print(f"{Colors.BOLD}{Colors.HEADER}Recherche avancée groupe/canal par mots-clés{Colors.ENDC}\n")
    client = await connect_client(account)
    if client is None:
        print(f"{Colors.FAIL}Impossible de connecter le compte {account['phone']}.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    query = input("Entrez les mots-clés à rechercher (séparés par des espaces) : ").strip()
    if not query:
        print(f"{Colors.WARNING}Recherche annulée (pas de mots-clés donnés).{Colors.ENDC}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    keywords = query.lower().split()
    print(f"{Colors.OKBLUE}Recherche en cours dans vos groupes et canaux...{Colors.ENDC}")

    matches = []
    try:
        dialogs = await client(GetDialogsRequest(offset_date=None, offset_id=0,
                offset_peer=InputPeerEmpty(), limit=300, hash=0))
        me = await client.get_me()
        for chat in dialogs.chats:
            title = getattr(chat, 'title', '').lower()
            if not title:
                continue
            if any(kw in title for kw in keywords):
                # Vérifier si déjà membre
                try:
                    full = await client(GetFullChannelRequest(channel=chat))
                    if me.id not in [u.user_id if hasattr(u, 'user_id') else None for u in full.full_chat.participants.participants]:
                        matches.append((chat, "Titre"))
                except:
                    # En cas d'erreur, ajouter quand même
                    matches.append((chat, "Titre"))
                continue
            # Recherche dans description si possible
            desc = ""
            try:
                full = await client(GetFullChannelRequest(channel=chat))
                desc = getattr(full.full_chat, 'about', "") or ""
            except:
                desc = ""
            desc = desc.lower()
            if any(kw in desc for kw in keywords):
                try:
                    full = await client(GetFullChannelRequest(channel=chat))
                    if me.id not in [u.user_id if hasattr(u, 'user_id') else None for u in full.full_chat.participants.participants]:
                        matches.append((chat, "Description"))
                except:
                    matches.append((chat, "Description"))
    except Exception as e:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Recherche groupes/canaux : {e}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    if not matches:
        print(f"{Colors.WARNING}Aucun groupe ou canal ne correspond aux mots-clés fournis ou déjà membre de tous.{Colors.ENDC}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    print(f"{Colors.OKGREEN}Groupes/canaux trouvés (où vous n'êtes pas membre) :{Colors.ENDC}")
    for i, (chat, source) in enumerate(matches, 1):
        g_type = 'Canal' if getattr(chat, 'broadcast', False) else 'Groupe'
        print(f"{Colors.OKCYAN}{i}{Colors.ENDC} - [{g_type}] {chat.title} (trouvé dans : {source})")

    choices = input("\nEntrez les numéros des groupes/canaux à rejoindre, séparés par des virgules, ou appuyez sur Entrée pour annuler : ").strip()
    if not choices:
        print("Action annulée.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    try:
        indices = [int(ch.strip()) for ch in choices.split(',') if ch.strip().isdigit()]
    except Exception:
        print("Entrée invalide.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    to_join = []
    for idx in indices:
        if 1 <= idx <= len(matches):
            to_join.append(matches[idx -1][0])

    if not to_join:
        print("Aucun groupe/canal valide sélectionné.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    confirm = input(f"{Colors.WARNING}Confirmez-vous rejoindre les {len(to_join)} groupes/canaux sélectionnés ? (o/N) : {Colors.ENDC}").strip().lower()
    if confirm != 'o':
        print("Action annulée.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    joined_count = 0
    for group in to_join:
        try:
            await client(JoinChannelRequest(channel=group))
            print(f"{Colors.OKGREEN}Vous avez rejoint {group.title}.{Colors.ENDC}")
            joined_count += 1
        except Exception as e:
            print(f"{Colors.FAIL}Erreur lors de la tentative de rejoindre {group.title} : {e}{Colors.ENDC}")
        await asyncio.sleep(BASE_DELAY_BETWEEN_ADDS + random.uniform(-3, 3))

    print(f"{Colors.OKGREEN}{joined_count} groupes/canaux rejoints avec succès.{Colors.ENDC}")

    await disconnect_client(account)
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# === QUITTER PLUSIEURS GROUPES ET CANAUX ===
async def leave_multiple_groups_channels(account):
    clear_screen()
    print(f"{Colors.BOLD}{Colors.HEADER}Quitter plusieurs groupes/canaux{Colors.ENDC}\n")

    client = await connect_client(account)
    if client is None:
        print(f"{Colors.FAIL}Impossible de connecter le compte {account['phone']}.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    groups_channels = await get_all_groups_channels(client)
    if not groups_channels:
        print(f"{Colors.WARNING}Aucun groupe/canal trouvé.{Colors.ENDC}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    print("Liste des groupes/canaux :")
    for i, g in enumerate(groups_channels, 1):
        g_type = 'Canal' if getattr(g, 'broadcast', False) else 'Groupe'
        print(f"{Colors.OKCYAN}{i}{Colors.ENDC} - [{g_type}] {g.title}")

    choices = input("\nEntrez les numéros des groupes/canaux à quitter, séparés par des virgules : ").strip()
    if not choices:
        print("Action annulée.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    try:
        indices = [int(ch.strip()) for ch in choices.split(',') if ch.strip().isdigit()]
    except Exception:
        print("Entrée invalide.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    to_leave = []
    for idx in indices:
        if 1 <= idx <= len(groups_channels):
            to_leave.append(groups_channels[idx -1])

    if not to_leave:
        print("Aucun groupe/canal valide sélectionné.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    confirm = input(f"{Colors.FAIL}Confirmez-vous quitter les {len(to_leave)} groupes/canaux sélectionnés ? (o/N) : {Colors.ENDC}").strip().lower()
    if confirm != 'o':
        print("Action annulée.")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    for group in to_leave:
        try:
            # Conversion vers InputChannel requise pour la requête LeaveChannelRequest
            input_channel = InputChannel(group.id, group.access_hash)
            await client(LeaveChannelRequest(input_channel))
            print(f"{Colors.OKGREEN}Quitte {group.title} avec succès.{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}Erreur en quittant {group.title}: {e}{Colors.ENDC}")
        await asyncio.sleep(BASE_DELAY_BETWEEN_ADDS + random.uniform(-3, 3))

    await disconnect_client(account)
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# === MENU PRINCIPAL ET BOUCLE ===
def print_menu():
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}=== MENU PRINCIPAL ==={Colors.ENDC}")
    print(f"{Colors.YELLOW}GESTION DES COMPTES{Colors.ENDC}")
    print(f"{Colors.OKCYAN}1{Colors.ENDC} - Ajouter un compte")
    print(f"{Colors.OKCYAN}2{Colors.ENDC} - État des comptes")
    print(f"{Colors.OKCYAN}3{Colors.ENDC} - Retrait d'un compte")
    print(f"{Colors.OKCYAN}4{Colors.ENDC} - Mise à jour & Actualisation des comptes")
    print(f"{Colors.OKBLUE}RÉCUPÉRATIONS, AJOUTS/MESSAGE{Colors.ENDC}")
    print(f"{Colors.OKCYAN}5{Colors.ENDC} - Choix groupe/canal source")
    print(f"{Colors.OKCYAN}6{Colors.ENDC} - Choix groupe/canal cible & ajout membres")
    print(f"{Colors.OKCYAN}7{Colors.ENDC} - Envoi de message en masse au groupe/canal source")
    print(f"{Colors.OKGREEN}RETIRER/REJOINDRE/QUITTER{Colors.ENDC}")
    print(f"{Colors.OKCYAN}8{Colors.ENDC} - Retrait membres inactifs")
    print(f"{Colors.OKCYAN}9{Colors.ENDC} - Recherche avancée groupe/canal (avec option rejoindre multiple)")
    print(f"{Colors.OKCYAN}10{Colors.ENDC} - Quitter plusieurs groupes/canaux")
    print(f"{Colors.OKGREEN}VUES/REACTIONS/SONDAGE{Colors.ENDC}")
    print(f"{Colors.OKCYAN}11{Colors.ENDC} - Augmenter de vues des pubs sans compte (canaux uniquement)")
    print(f"{Colors.OKCYAN}12{Colors.ENDC} - Réactions aux pubs/messages")
    print(f"{Colors.OKCYAN}13{Colors.ENDC} - Sondage/Votes")
    print(f"{Colors.OKGREEN}MENU FEU{Colors.ENDC}")
    print(f"{Colors.OKCYAN}14{Colors.ENDC} - Créer un API ID & API HASH")
    print(f"{Colors.OKCYAN}15{Colors.ENDC} - Signaler un compte/groupe/canal")
    print(f"{Colors.OKGREEN}AUTRES{Colors.ENDC}")
    print(f"{Colors.OKCYAN}16{Colors.ENDC} - Actualiser & Correction intelligent du script")
    print(f"{Colors.OKCYAN}99{Colors.ENDC} - Quitter\n")

def access_code_prompt():
    clear_screen()
    for _ in range(3):
        code = input(f"{Colors.BOLD}Entrez le code d'accès : {Colors.ENDC}").strip()
        if code == '0797':
            return True
        print(f"{Colors.FAIL}Code incorrect.{Colors.ENDC}")
    print(f"{Colors.FAIL}Accès refusé.{Colors.ENDC}")
    return False

def main_loop():
    global GROUP_SOURCE, GROUP_TARGET, GROUP_INVITE_LINK, MESSAGE_TO_SEND

    load_accounts()
    while True:
        print_menu()
        choice = input(f"{Colors.BOLD}Choix (numéro) : {Colors.ENDC}").strip()

        loop = asyncio.get_event_loop()

        if choice == '1':
            acc = input_account()
            if acc:
                existing = next((a for a in ACCOUNTS if a['phone'] == acc['phone']), None)
                if existing:
                    existing.update(acc)
                    print(f"{Colors.OKGREEN}Compte {acc['phone']} mis à jour.{Colors.ENDC}")
                else:
                    ACCOUNTS.append(acc)
                    print(f"{Colors.OKGREEN}Compte {acc['phone']} ajouté.{Colors.ENDC}")
                save_accounts()
                input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

        elif choice == '2':
            show_accounts()
        elif choice == '3':
            remove_account()
        elif choice == '4':
            loop.run_until_complete(refresh_all_accounts())
        elif choice == '5':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]
            grp_source = loop.run_until_complete(choose_group_channel(account, "source"))
            if grp_source:
                GROUP_SOURCE = grp_source
                print(f"{Colors.OKGREEN}Groupe/canal source configuré : {grp_source.title}{Colors.ENDC}")
            input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        elif choice == '6':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]
            grp_target = loop.run_until_complete(choose_group_channel(account, "cible"))
            if grp_target:
                GROUP_TARGET = grp_target
                print(f"{Colors.OKGREEN}Groupe/canal cible configuré : {grp_target.title}{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée pour lancer l'ajout...{Colors.ENDC}")
                loop.run_until_complete(run_addition())
            else:
                print(f"{Colors.FAIL}Aucun groupe/canal cible sélectionné.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        elif choice == '7':
            loop.run_until_complete(mass_message())
        elif choice == '8':
            loop.run_until_complete(remove_inactive_members())
        elif choice == '9':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]
            loop.run_until_complete(advanced_search_group_channel(account))
        elif choice == '10':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]
            loop.run_until_complete(leave_multiple_groups_channels(account))
        elif choice == '11':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]
            loop.run_until_complete(increase_views(account))
        elif choice == '12':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]
            loop.run_until_complete(react_to_message(account))
        elif choice == '13':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]
            loop.run_until_complete(create_poll(account))
        elif choice == '14':
            create_api_id_hash_info()
        elif choice == '15':
            report_account_group_channel()
        elif choice == '16':
            loop.run_until_complete(refresh_script())
        elif choice == '99':
            clear_screen()
            print(f"{Colors.BOLD}{Colors.OKCYAN}Au revoir !{Colors.ENDC}")
            sys.exit(0)
        else:
            print(f"{Colors.FAIL}Choix invalide.{Colors.ENDC}")
            time.sleep(1)

# === EXÉCUTION PRINCIPALE ===
if __name__ == '__main__':
    if not access_code_prompt():
        sys.exit(1)
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}=== Gestionnaire Telegram multi-comptes optimisé ==={Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour démarrer...{Colors.ENDC}")
    main_loop()

