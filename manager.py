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

import asyncio
import random
import time
import os
import sys
import json
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetParticipantsRequest, InviteToChannelRequest, JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest, GetFullChatRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusRecently, UserStatusOffline, UserStatusOnline, InputPeerEmpty
from telethon.utils import get_input_peer

# Constantes couleurs ANSI
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

# Paramètres constants
BASE_DELAY_BETWEEN_ADDS = 12
BASE_DELAY_BETWEEN_ACCOUNTS = 45
MEMBERS_PER_ACCOUNT = 8
MEMBER_CACHE_TTL = 3600  # 1 heure cache membres

SESSION_DIR = './sessions'
if not os.path.isdir(SESSION_DIR):
    os.mkdir(SESSION_DIR)

ACCOUNTS_FILE = 'accounts.json'

# Globals
ACCOUNTS = []
GROUP_SOURCE = None
GROUP_TARGET = None
GROUP_INVITE_LINK = None
MESSAGE_TO_SEND = None

MEMBERS_CACHE = {'timestamp': 0, 'members': []}

# === UTILITAIRES

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

# === GESTION COMPTES

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

# === UTILITAIRES MEMBRES ET GROUPES/CANAUX

def is_user_active_recently(user):
    status = getattr(user, 'status', None)
    if status is None:
        return False
    if isinstance(status, UserStatusRecently) or isinstance(status, UserStatusOnline):
        return True
    if isinstance(status, UserStatusOffline):
        if status.was_online is None:
            return False
        now = datetime.now(timezone.utc)
        delta = timedelta(days=7)
        was_online = status.was_online
        if was_online.tzinfo is None:
            was_online = was_online.replace(tzinfo=timezone.utc)
        return (now - was_online) <= delta
    return False

async def get_all_groups_channels(client):
    # Obtenir tous les groupes et canaux (megagroups + channels)
    groups_channels = []
    try:
        dialogs = await client(GetDialogsRequest(offset_date=None, offset_id=0,
                offset_peer=InputPeerEmpty(), limit=300, hash=0))
        for chat in dialogs.chats:
            # On prend megagroups (groupes) et channels publics/privés pour ciblage
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

async def get_all_active_members(client, group_channel):
    global MEMBERS_CACHE
    now_ts = time.time()
    if MEMBERS_CACHE["timestamp"] + MEMBER_CACHE_TTL > now_ts and MEMBERS_CACHE["members"]:
        print(f"{Colors.OKBLUE}Utilisation du cache membres moins de {MEMBER_CACHE_TTL//60} minutes.{Colors.ENDC}")
        return MEMBERS_CACHE["members"]
    all_users = []
    offset = 0
    limit = 100
    print(f"{Colors.OKBLUE}Récupération des membres actifs dans {group_channel.title} ...{Colors.ENDC}")
    try:
        while True:
            participants = await client(GetParticipantsRequest(channel=group_channel,
                    filter=ChannelParticipantsSearch(''), offset=offset, limit=limit, hash=0))
            if not participants.users:
                break
            filtered = [user for user in participants.users if is_user_active_recently(user)]
            all_users.extend(filtered)
            offset += len(participants.users)
    except Exception as e:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Récupération membres: {e}")
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

# === FONCTIONNALITES RECUPERATIONS, AJOUTS/MESSAGE

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
    temp_client = await connect_client(ACCOUNTS[0])
    if temp_client is None:
        print(f"{Colors.FAIL}Impossible de connecter le premier compte.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return
    members = await get_all_active_members(temp_client, GROUP_SOURCE)
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
        print(f"{Colors
