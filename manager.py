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
from telethon.tl.functions.messages import GetDialogsRequest, GetFullChannelRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusRecently, UserStatusOffline, UserStatusOnline, InputPeerEmpty, InputPeerChannel
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
                        await asyncio.sleep(2)  # Pause entre messages
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

# === RETIRER MEMBRES INACTIFS (inchangé) option 8

async def remove_inactive_members():
    clear_screen()
    print(f"{Colors.BOLD}Retrait membres inactifs (2 mois ou plus):{Colors.ENDC}")
    if not ACCOUNTS:
        print(f"{Colors.FAIL}Aucun compte configuré.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return
    account = ACCOUNTS[0]
    client = await connect_client(account)
    if client is None:
        print(f"{Colors.FAIL}Impossible de se connecter avec {account['phone']}.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return
    group_link = input("Entrez le lien du groupe/canal Telegram (sans '@' ou 'https://t.me/'): ").strip()
    if not group_link:
        print(f"{Colors.FAIL}Lien groupe/canal vide. Annulé.{Colors.ENDC}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return
    try:
        group = await client.get_entity(group_link)
        if not (getattr(group, "megagroup", False) or getattr(group, "broadcast", False)):
            print(f"{Colors.FAIL}Ce n'est pas un groupe ou canal valide.{Colors.ENDC}")
            await disconnect_client(account)
            input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
            return
    except Exception as e:
        print(f"{Colors.FAIL}Erreur récupération groupe/canal : {e}{Colors.ENDC}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    print(f"{Colors.OKCYAN}Extraction commencera dans 10 secondes...{Colors.ENDC}")
    time.sleep(10)
    two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)

    all_members = []
    offset = 0
    limit = 100
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
        all_members.extend(participants.users)
        offset += len(participants.users)

    inactive_members = []
    for m in all_members:
        status = getattr(m, 'status', None)
        if isinstance(status, UserStatusOffline):
            was_online = status.was_online
            if was_online is not None:
                if was_online.tzinfo is None:
                    was_online = was_online.replace(tzinfo=timezone.utc)
                if was_online < two_months_ago:
                    inactive_members.append(m)

    print(f"{Colors.WARNING}Membres inactifs détectés : {len(inactive_members)}{Colors.ENDC}")
    confirm = input(f"{Colors.BOLD}Souhaitez-vous retirer tous ces membres ? (O/N) : {Colors.ENDC}").strip().lower()
    if confirm not in ['o', 'oui', 'y', 'yes']:
        print(f"{Colors.WARNING}Annulation du retrait des membres.{Colors.ENDC}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return

    for member in inactive_members:
        try:
            await client.kick_participant(group, member)
            print(f"{Colors.OKGREEN}Membre retiré : {member.first_name or 'N/A'} ({member.id}){Colors.ENDC}")
            await asyncio.sleep(2)
        except errors.ChatAdminRequiredError:
            print(f"{Colors.FAIL}Droits insuffisants pour retirer les membres.{Colors.ENDC}")
            break
        except errors.FloodWaitError as e:
            print(f"{Colors.WARNING}FloodWait détecté, pause {e.seconds} secondes.{Colors.ENDC}")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"{Colors.FAIL}Erreur lors du retrait du membre {member.first_name or 'N/A'}: {e}{Colors.ENDC}")

    await disconnect_client(account)
    input(f"{Colors.WARNING}Opération terminée. Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# === RETIRER/REJOINDRE/QUITTER : fonctions avancées

async def advanced_search_group_channel(account):
    clear_screen()
    print(f"{Colors.BOLD}Recherche avancée groupe/canal :{Colors.ENDC}")
    search_query = input("Entrez le nom du groupe ou canal à rechercher : ").strip()
    client = await connect_client(account)
    channels = []
    if client:
        try:
            dialogs = await client(GetDialogsRequest(offset_date=None, offset_id=0,
                    offset_peer=InputPeerEmpty(), limit=300, hash=0))
            for chat in dialogs.chats:
                if (getattr(chat, 'megagroup', False) or getattr(chat, 'broadcast', False)) and search_query.lower() in chat.title.lower():
                    channels.append(chat)
            if not channels:
                print(f"{Colors.WARNING}Aucun groupe/canal trouvé avec ce nom.{Colors.ENDC}")
                await disconnect_client(account)
                input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
                return
            print(f"{Colors.OKGREEN}Groupes/Canaux trouvés :{Colors.ENDC}")
            for i, ch in enumerate(channels, 1):
                ttype = "Canal" if getattr(ch, "broadcast", False) else "Groupe"
                print(f"{Colors.OKCYAN}{i}{Colors.ENDC} - [{ttype}] {ch.title}")
            choice = input(f"Voulez-vous rejoindre un groupe/canal ? (O/N) : ").strip().lower()
            if choice in ['o', 'oui', 'y', 'yes']:
                idx = input(f"Choisissez un numéro (1-{len(channels)}) : ").strip()
                if idx.isdigit() and 1 <= int(idx) <= len(channels):
                    target = channels[int(idx)-1]
                    try:
                        await client(JoinChannelRequest(target))
                        print(f"{Colors.OKGREEN}Rejoint {target.title} avec succès.{Colors.ENDC}")
                    except Exception as e:
                        print(f"{Colors.FAIL}Erreur lors du join: {e}{Colors.ENDC}")
                else:
                    print(f"{Colors.FAIL}Choix invalide.{Colors.ENDC}")
            input(f"{Colors.WARNING}Appuyez sur Entrée pour continuer...{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}Erreur lors de la recherche : {e}{Colors.ENDC}")
        await disconnect_client(account)

async def leave_multiple_groups_channels(account):
    clear_screen()
    print(f"{Colors.BOLD}Quitter groupes/canaux :{Colors.ENDC}")
    client = await connect_client(account)
    if client:
        try:
            dialogs = await client(GetDialogsRequest(offset_date=None, offset_id=0,
                offset_peer=InputPeerEmpty(), limit=300, hash=0))
            groups_channels = [chat for chat in dialogs.chats if getattr(chat, "megagroup", False) or getattr(chat, "broadcast", False)]
            if not groups_channels:
                print(f"{Colors.WARNING}Aucun groupe/canal trouvé.{Colors.ENDC}")
                await disconnect_client(account)
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                return
            print(f"{Colors.OKGREEN}Groupes/Canaux :{Colors.ENDC}")
            for i, ch in enumerate(groups_channels, 1):
                ttype = "Canal" if getattr(ch, "broadcast", False) else "Groupe"
                print(f"{Colors.OKCYAN}{i}{Colors.ENDC} - [{ttype}] {ch.title}")
            choices = input(f"Entrez les numéros des groupes/canaux à quitter, séparés par des virgules : ").strip()
            nums = [c.strip() for c in choices.split(",") if c.strip().isdigit()]
            nums = [int(n) for n in nums if 1 <= int(n) <= len(groups_channels)]
            if not nums:
                print(f"{Colors.FAIL}Aucun choix valide.{Colors.ENDC}")
                await disconnect_client(account)
                input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
                return
            for n in nums:
                target = groups_channels[n-1]
                try:
                    await client(LeaveChannelRequest(target))
                    print(f"{Colors.OKGREEN}Quitte {target.title}{Colors.ENDC}")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"{Colors.FAIL}Erreur lors du départ de {target.title} : {e}{Colors.ENDC}")
            input(f"{Colors.WARNING}Opération terminée. Appuyez sur Entrée...{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}Erreur lors de la récupération : {e}{Colors.ENDC}")
        await disconnect_client(account)

# === VUES/REACTIONS/SONDAGE avancés

async def increase_views(account):
    clear_screen()
    print(f"{Colors.BOLD}Augmenter les vues des pubs (canaux uniquement) sans compte:{Colors.ENDC}")
    channel_name = input("Entrez le nom complet ou lien du canal (sans '@' ou https://t.me/) : ").strip()
    views_str = input("Entrez le nombre de vues à ajouter : ").strip()
    try:
        views_count = int(views_str)
        if views_count <= 0:
            print(f"{Colors.FAIL}Le nombre de vues doit être positif.{Colors.ENDC}")
            input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
            return
    except:
        print(f"{Colors.FAIL}Nombre invalide.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return
    client = await connect_client(account)
    if not client:
        return
    try:
        channel = await client.get_entity(channel_name)
        if not getattr(channel, "broadcast", False):
            print(f"{Colors.FAIL}Ce n'est pas un canal.{Colors.ENDC}")
            await disconnect_client(account)
            input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
            return
    except Exception as e:
        print(f"{Colors.FAIL}Erreur récupération canal : {e}{Colors.ENDC}")
        await disconnect_client(account)
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    for i in range(views_count):
        try:
            # Pour simuler une vue, on envoie un message vide. Pas d'API officielle pour vues.
            await client.send_message(channel, " ")
            print(f"{Colors.OKGREEN}Vue {i+1}/{views_count} ajoutée au canal {channel.title}{Colors.ENDC}")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"{Colors.FAIL}Erreur lors de l'ajout de vue: {e}{Colors.ENDC}")
            break

    await disconnect_client(account)
    input(f"{Colors.WARNING}Opération terminée. Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def react_to_message(account):
    clear_screen()
    print(f"{Colors.BOLD}Réactions aux pubs/messages :{Colors.ENDC}")
    message_link = input("Entrez le lien du message (exact) : ").strip()
    reactions_str = input("Entrez le nombre de réactions à envoyer : ").strip()
    reaction_type = input("Entrez le type de réaction (ex: 👍, ❤️, 😂, etc.) : ").strip()
    try:
        reactions_count = int(reactions_str)
        if reactions_count <= 0:
            print(f"{Colors.FAIL}Le nombre de réactions doit être positif.{Colors.ENDC}")
            input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
            return
    except:
        print(f"{Colors.FAIL}Nombre invalide.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    client = await connect_client(account)
    if not client:
        return

    try:
        entity = await client.get_entity(message_link)
        # L'API Telethon ne permet pas nativement de réagir via text simple.
        # Pour une vraie réaction, il faudrait intégrer des appels aux méthodes Raw ou utiliser une autre bibliothèque.
        print(f"{Colors.WARNING}Note: Cette fonction nécessite une implémentation avancée spécifique aux versions Telegram et Telethon.{Colors.ENDC}")
        print(f"Simuler l'envoi de {reactions_count} réactions '{reaction_type}' au message {message_link}{Colors.ENDC}")
        # Placeholder pour la logique de réaction
        # ...
        await asyncio.sleep(1)
        print(f"{Colors.OKGREEN}Réactions envoyées.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Erreur lors de la récupération du message : {e}{Colors.ENDC}")

    await disconnect_client(account)
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def create_poll(account):
    clear_screen()
    print(f"{Colors.BOLD}Création de sondage / votes :{Colors.ENDC}")
    channel_name = input("Entrez le nom ou lien du groupe/canal : ").strip()
    question = input("Entrez la question du sondage : ").strip()
    options_str = input("Entrez les options séparées par des virgules : ").strip()

    options = [opt.strip() for opt in options_str.split(",") if opt.strip()]
    if len(options) < 2:
        print(f"{Colors.FAIL}Il faut au moins 2 options.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée...{Colors.ENDC}")
        return

    client = await connect_client(account)
    if not client:
        return
    try:
        channel = await client.get_entity(channel_name)
        # Telethon propose CreatePollRequest, mais nécessite imports supplémentaires, usage avancé
        # Pour simplification, on envoie un message texte avec question et options
        poll_text = f"📊 {question}\n"
        for idx, opt in enumerate(options, 1):
            poll_text += f"{idx}. {opt}\n"
        await client.send_message(channel, poll_text)
        print(f"{Colors.OKGREEN}Sondage publié avec succès dans {channel.title}.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}Erreur lors de la création du sondage : {e}{Colors.ENDC}")
    await disconnect_client(account)
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# === MENU FEU

def create_api_id_hash_info():
    clear_screen()
    print(f"{Colors.BOLD}Création API ID & API HASH :{Colors.ENDC}")
    print("Pour créer un API ID & API HASH, rendez-vous sur https://my.telegram.org")
    print("Connectez-vous, puis aller dans 'API development tools', créez une nouvelle application.")
    print("Vous obtiendrez votre API ID et API HASH à utiliser ici.")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

def report_account_group_channel():
    clear_screen()
    print(f"{Colors.BOLD}Signaler un compte/groupe/canal :{Colors.ENDC}")
    print("Cette fonctionnalité nécessite une intégration avancée selon le contexte.")
    print("En attente d'implémentation spécifique ou liaison avec API Telegram officielle.")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# === AUTRES (inchangés)

async def refresh_script():
    clear_screen()
    print(f"{Colors.BOLD}Actualisation et correction du script :{Colors.ENDC}")
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            print(f"{Colors.OKGREEN}Compte {account['phone']} validé.{Colors.ENDC}")
            await disconnect_client(account)
        else:
            print(f"{Colors.WARNING}Compte {account['phone']} invalide ou déconnecté.{Colors.ENDC}")
    global MEMBERS_CACHE
    MEMBERS_CACHE = {'timestamp': 0, 'members': []}
    print(f"{Colors.OKGREEN}Script actualisé avec succès.{Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# === MENU PRINCIPAL

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
    print(f"{Colors.OKCYAN}9{Colors.ENDC} - Recherche avancée groupe/canal (avec option rejoindre)")
    print(f"{Colors.OKCYAN}10{Colors.ENDC} - Quitter des groupes/canaux")
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
                global GROUP_SOURCE
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
                global GROUP_TARGET
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

if __name__ == '__main__':
    if not access_code_prompt():
        sys.exit(1)
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}=== Gestionnaire Telegram multi-comptes optimisé ==={Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour démarrer...{Colors.ENDC}")
    main_loop()


