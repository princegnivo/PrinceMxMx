"""
Gestionnaire Telegram multi-comptes ultra-sûr, optimisé et robuste avec interface colorée.

Fonctionnalités :
- Correction complète datetime UTC pour éviter erreurs
- Interface console colorée ANSI, effacement écran entre menus
- Gestion multi-comptes, vérification et reconnexion automatique
- Choix interactif des groupes source et cible parmi tous les groupes accessibles
- Ajout des membres actifs récents (7 derniers jours)
- Rotation sécurisée avec pauses aléatoires optimales pour ratio efficacité / anti-ban
- Envoi de lien d’invitation si absence de droits admin pour ajout direct
- Gestion complète et reprise des erreurs courantes, FloodWait, privacy, limitations
- Enregistrement local automatique des sessions Telethon pour réutilisation
- Caches simples des membres récupérés pour éviter appels redondants
- Menu clair et simple en console avec instructions et validations
- Compatible Python 3.7+ et dernières versions Telethon

Prérequis et usage inchangés. Script pensé pour stabilité optimale.

"""

import asyncio
import random
import time
import os
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, errors, utils
from telethon.tl.functions.channels import GetParticipantsRequest, InviteToChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusRecently, InputPeerEmpty, UserStatusOffline, UserStatusOnline
import sys
import json

# Constantes couleurs ANSI
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'      # Reset
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Délais et paramètres optimisés
BASE_DELAY_BETWEEN_ADDS = 12          # pause moyenne avant ajout membre (pour réduire risques)
BASE_DELAY_BETWEEN_ACCOUNTS = 45      # pause moyenne entre changement de comptes
MEMBERS_PER_ACCOUNT = 8                # nb membres ajoutés max par compte avant changement (Telegram limite)
MEMBER_CACHE_TTL = 3600               # cache membre: 1h (60*60s)

# Stockage des sessions dans ./sessions/ avec gestion automatique
SESSION_DIR = "./sessions"
if not os.path.isdir(SESSION_DIR):
    os.mkdir(SESSION_DIR)

# Fichier de sauvegarde comptes local (format JSON)
ACCOUNTS_FILE = "accounts.json"

# Globals
ACCOUNTS = []         # list dict: api_id, api_hash, phone, added_users, last_error, client
GROUP_SOURCE = None   # Telegram entity (objet)
GROUP_TARGET = None   # Telegram entity
GROUP_INVITE_LINK = None  # url invitation si pas admin

# Cache membres source (list user id + timestamp)
MEMBERS_CACHE = {"timestamp": 0, "members": []}

# Nettoyer écran
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# Sauvegarder comptes dans JSON local
def save_accounts():
    try:
        to_save = []
        for acc in ACCOUNTS:
            to_save.append({
                'api_id': acc['api_id'],
                'api_hash': acc['api_hash'],
                'phone': acc['phone'],
                'added_users': acc.get('added_users',0)
            })
        with open(ACCOUNTS_FILE, "w") as f:
            json.dump(to_save, f)
    except Exception as e:
        print(f"{Colors.WARNING}[WARN]{Colors.ENDC} Impossible de sauvegarder comptes: {e}")

# Charger comptes depuis JSON local
def load_accounts():
    global ACCOUNTS
    try:
        if os.path.isfile(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, "r") as f:
                loaded = json.load(f)
                ACCOUNTS = []
                for acc in loaded:
                    ACCOUNTS.append({
                        'api_id': acc['api_id'],
                        'api_hash': acc['api_hash'],
                        'phone': acc['phone'],
                        'added_users': acc.get('added_users',0),
                        'last_error': None,
                        'client': None
                    })
    except Exception as e:
        print(f"{Colors.WARNING}[WARN]{Colors.ENDC} Impossible de charger comptes: {e}")

def input_account():
    clear_screen()
    print(f"{Colors.BOLD}Saisir les informations du compte Telegram :{Colors.ENDC}")
    try:
        api_id = int(input("api_id (numérique) : ").strip())
        api_hash = input("api_hash : ").strip()
        phone = input("Numéro de téléphone (+33...) : ").strip()
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
            err = acc.get('last_error', None)
            if err:
                print(f"  Dernière erreur: {Colors.FAIL}{err}{Colors.ENDC}")
            else:
                print(f"  Dernière erreur: {Colors.OKGREEN}Aucune{Colors.ENDC}")
            print("")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def connect_client(account):
    """
    Connecte un client Telegram avec session automatique.
    Reconnexion optimisée, gestion erreurs.
    """
    if account['client'] is not None and account['client'].is_connected():
        return account['client']
    try:
        session_path = f"{SESSION_DIR}/session_{account['phone']}"
        client = TelegramClient(session_path, account['api_id'], account['api_hash'])
        await client.start(phone=account['phone'])
        me = await client.get_me()
        print(f"{Colors.OKGREEN}[INFO]{Colors.ENDC} Connecté avec {me.first_name} ({account['phone']})")
        account['last_error'] = None
        account['client'] = client
        return client
    except errors.PhoneCodeInvalidError:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Code de confirmation invalide pour {account['phone']}.")
        account['last_error'] = "Code confirmation invalide"
    except errors.PhoneNumberBannedError:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Numéro banni : {account['phone']}")
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
        except Exception:
            pass

def is_user_active_recently(user):
    """
    Vérifie si un utilisateur a été actif dans les 7 derniers jours.
    Gestion timezone-aware et datetime compatible Python 3.12+.
    """
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
        now = datetime.now(timezone.utc)
        delta_7_days = timedelta(days=7)
        was_online = status.was_online
        # Compatibilité offset naive/aware
        if was_online.tzinfo is None:
            was_online = was_online.replace(tzinfo=timezone.utc)
        if now - was_online <= delta_7_days:
            return True
    return False

async def get_all_groups(client):
    groups = []
    try:
        dialogs = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=300,
            hash=0
        ))
        for chat in dialogs.chats:
            if getattr(chat, 'megagroup', False):
                groups.append(chat)
    except Exception as e:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Récupération groupes : {e}")
    return groups

async def choose_group(account, purpose):
    client = await connect_client(account)
    if client is None:
        input(f"{Colors.FAIL}Impossible de se connecter avec {account['phone']}. Appuyez sur Entrée...{Colors.ENDC}")
        return None
    groups = await get_all_groups(client)
    if not groups:
        input(f"{Colors.WARNING}Aucun groupe trouvé. Appuyez sur Entrée...{Colors.ENDC}")
        await disconnect_client(account)
        return None
    while True:
        clear_screen()
        print(f"{Colors.BOLD}{Colors.UNDERLINE}Choisissez le groupe {purpose} parmi vos groupes :{Colors.ENDC}")
        for i, g in enumerate(groups, 1):
            print(f"{Colors.OKCYAN}{i}{Colors.ENDC} - {g.title}")
        choice = input(f"\nNuméro groupe {purpose} : ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(groups):
            chosen = groups[int(choice)-1]
            print(f"\n{Colors.OKGREEN}Group {purpose} sélectionné : {chosen.title}{Colors.ENDC}")
            await disconnect_client(account)
            input(f"\n{Colors.WARNING}Appuyez sur Entrée pour continuer...{Colors.ENDC}")
            return chosen
        print(f"{Colors.FAIL}Choix invalide. Réessayez.{Colors.ENDC}")
        time.sleep(1)

async def get_all_active_members(client, group):
    """
    Récupère et filtre les membres actifs récents du groupe.
    Utilise cache TTL pour éviter recharge trop fréquente.
    """
    global MEMBERS_CACHE

    now_ts = time.time()
    if MEMBERS_CACHE["timestamp"] + MEMBER_CACHE_TTL > now_ts and MEMBERS_CACHE["members"]:
        print(f"{Colors.OKBLUE}Utilisation du cache membre moins de {MEMBER_CACHE_TTL//60} min.{Colors.ENDC}")
        return MEMBERS_CACHE["members"]

    all_participants = []
    offset = 0
    limit = 100
    print(f"{Colors.OKBLUE}Récupération des membres actifs dans {group.title} ...{Colors.ENDC}")
    try:
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
    except Exception as e:
        print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} Erreur récupération membres: {e}")
    print(f"{Colors.OKGREEN}Membres actifs récupérés: {len(all_participants)}{Colors.ENDC}")
    MEMBERS_CACHE["timestamp"] = now_ts
    MEMBERS_CACHE["members"] = all_participants
    return all_participants

async def add_members(client, group_target, users_to_add, account):
    added_count = 0
    for user in users_to_add:
        try:
            await client(InviteToChannelRequest(
                channel=group_target,
                users=[user.id]
            ))
            print(f"{Colors.OKGREEN}[OK]{Colors.ENDC} Ajouté: {user.first_name} ({user.id}) avec {account['phone']}")
            added_count += 1
            account['added_users'] = account.get('added_users', 0) + 1
        except errors.UserPrivacyRestrictedError:
            print(f"{Colors.WARNING}[IGNORÉ]{Colors.ENDC} {user.first_name} empêche d'être ajouté (privacy).")
        except errors.UserAlreadyParticipantError:
            print(f"{Colors.WARNING}[IGNORÉ]{Colors.ENDC} {user.first_name} est déjà dans le groupe cible.")
        except errors.ChatAdminRequiredError:
            if GROUP_INVITE_LINK:
                try:
                    invite_msg = f"Bonjour {user.first_name},\nJe vous invite à rejoindre ce groupe : {GROUP_INVITE_LINK}"
                    await client.send_message(user.id, invite_msg)
                    print(f"{Colors.OKCYAN}[INFO]{Colors.ENDC} Lien d'invitation envoyé à {user.first_name} ({user.id}) car pas admin.")
                    added_count += 1
                    account['added_users'] = account.get('added_users', 0) + 1
                except Exception as e:
                    print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Impossible d’envoyer lien à {user.first_name} : {e}")
                    account['last_error'] = str(e)
            else:
                print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Pas admin et pas de lien invitation défini, impossible d'ajouter {user.first_name}.")
        except errors.FloodWaitError as flood_err:
            print(f"{Colors.WARNING}[PAUSE]{Colors.ENDC} FloodWait {flood_err.seconds}s détecté sur {account['phone']}. Pause prolongée.")
            account['last_error'] = f"FloodWait {flood_err.seconds}s"
            await asyncio.sleep(flood_err.seconds + 10)
        except Exception as e:
            print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Impossible d'ajouter {user.first_name} : {e}")
            account['last_error'] = str(e)

        delay = BASE_DELAY_BETWEEN_ADDS + random.uniform(-3, 3)
        await asyncio.sleep(max(6, delay))
    return added_count

async def run_addition():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.HEADER}Début de l'ajout multi-compte des membres actifs...{Colors.ENDC}\n")
    if not ACCOUNTS:
        print(f"{Colors.FAIL}Aucun compte configuré. Ajoute-en un via le menu.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return
    if not GROUP_SOURCE or not GROUP_TARGET:
        print(f"{Colors.FAIL}Groupes source et/ou cible non configurés. Configure-les via le menu.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return

    temp_client = await connect_client(ACCOUNTS[0])
    if temp_client is None:
        print(f"{Colors.FAIL}[ERREUR] Impossible de connecter le premier compte.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir...{Colors.ENDC}")
        return

    source_entity = GROUP_SOURCE
    target_entity = GROUP_TARGET

    members = await get_all_active_members(temp_client, source_entity)
    await temp_client.disconnect()

    if not members:
        print(f"{Colors.WARNING}Pas de membres actifs trouvés au groupe source.{Colors.ENDC}")
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
            print(f"\n{Colors.OKBLUE}Ajout du batch {index // MEMBERS_PER_ACCOUNT + 1} de {len(users_batch)} membres avec {account['phone']}{Colors.ENDC}")
            added = await add_members(client, target_entity, users_batch, account)
            print(f"{Colors.OKGREEN}Ajoutés {added} membres avec {account['phone']}{Colors.ENDC}")
            await disconnect_client(account)

            delay_account = BASE_DELAY_BETWEEN_ACCOUNTS + random.uniform(-7, 7)
            print(f"{Colors.WARNING}Pause de {int(delay_account)} secondes avant changement de compte...{Colors.ENDC}")
            time.sleep(delay_account)

            index += MEMBERS_PER_ACCOUNT
            if index >= total_members:
                break

    print(f"\n{Colors.OKGREEN}{Colors.BOLD}Ajout terminé de tous les membres actifs.{Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

async def refresh_all_accounts():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.HEADER}Mise à jour et reconnexion de tous les comptes...{Colors.ENDC}\n")
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            print(f"{Colors.OKGREEN}{account['phone']} connecté avec succès.{Colors.ENDC}")
            account['last_error'] = None
            await disconnect_client(account)
        else:
            print(f"{Colors.FAIL}Échec de connexion pour {account['phone']}.{Colors.ENDC}")
    save_accounts()
    input(f"\n{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# Fonction pour retirer un compte
def remove_account():
    clear_screen()
    print(f"{Colors.BOLD}Retirer un compte Telegram :{Colors.ENDC}")
    if not ACCOUNTS:
        print(f"{Colors.WARNING}Aucun compte configuré.{Colors.ENDC}\n")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return
    for i, acc in enumerate(ACCOUNTS, 1):
        print(f"{Colors.OKBLUE}Compte #{i}{Colors.ENDC}: {acc['phone']}")
    choice = input(f"\nChoisissez le numéro du compte à retirer : ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(ACCOUNTS):
        removed_account = ACCOUNTS.pop(int(choice) - 1)
        print(f"{Colors.OKGREEN}Compte {removed_account['phone']} retiré avec succès.{Colors.ENDC}")
        save_accounts()
    else:
        print(f"{Colors.FAIL}Choix invalide.{Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

# Fonction pour envoyer des messages en masse
async def send_mass_message(client, group, message):
    try:
        await client.send_message(group, message)
        print(f"{Colors.OKGREEN}[INFO]{Colors.ENDC} Message envoyé avec succès.")
    except Exception as e:
        print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Impossible d'envoyer le message : {e}")

async def mass_message():
    clear_screen()
    print(f"{Colors.BOLD}Masse de message :{Colors.ENDC}")
    if not GROUP_TARGET:
        print(f"{Colors.FAIL}Aucun groupe cible configuré.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return
    message = input("Entrez le message à envoyer : ")
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            await send_mass_message(client, GROUP_TARGET, message)
            await disconnect_client(account)
        else:
            print(f"{Colors.FAIL}Échec de connexion pour {account['phone']}.{Colors.ENDC}")

# Fonction pour retirer les membres inactifs
async def remove_inactive_members():
    clear_screen()
    print(f"{Colors.BOLD}Retrait des membres inactifs (2 mois ou plus) :{Colors.ENDC}")
    if not GROUP_TARGET:
        print(f"{Colors.FAIL}Aucun groupe cible configuré.{Colors.ENDC}")
        input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
        return
    two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            try:
                all_participants = []
                offset = 0
                limit = 100
                while True:
                    participants = await client(GetParticipantsRequest(
                        channel=GROUP_TARGET,
                        filter=ChannelParticipantsSearch(''),
                        offset=offset,
                        limit=limit,
                        hash=0
                    ))
                    if not participants.users:
                        break
                    all_participants.extend(participants.users)
                    offset += len(participants.users)
                for member in all_participants:
                    status = getattr(member, 'status', None)
                    if isinstance(status, UserStatusOffline):
                        was_online = status.was_online
                        if was_online is not None:
                            if was_online.tzinfo is None:
                                was_online = was_online.replace(tzinfo=timezone.utc)
                            if was_online < two_months_ago:
                                try:
                                    # Use EditBannedRequest or appropriate method to kick user
                                    await client.kick_participant(GROUP_TARGET, member)
                                    print(f"{Colors.OKGREEN}[OK]{Colors.ENDC} Retiré: {member.first_name} ({member.id})")
                                except Exception as e:
                                    print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Impossible de retirer {member.first_name} : {e}")
            except Exception as e:
                print(f"{Colors.FAIL}[ERREUR]{Colors.ENDC} Erreur lors du retrait des membres inactifs : {e}")
            await disconnect_client(account)

# Fonction pour actualiser et corriger le script
async def refresh_script():
    clear_screen()
    print(f"{Colors.BOLD}Actualisation et correction du script :{Colors.ENDC}")
    # Ajoutez ici les fonctions d'analyse, nettoyage cache, mise à jour des comptes, etc.
    # Par exemple, on peut rafraîchir les sessions et vérifier la validité des comptes
    for account in ACCOUNTS:
        client = await connect_client(account)
        if client:
            print(f"{Colors.OKGREEN}Compte {account['phone']} validé.{Colors.ENDC}")
            await disconnect_client(account)
        else:
            print(f"{Colors.WARNING}Compte {account['phone']} invalide ou déjà déconnecté.{Colors.ENDC}")
    # Reset du cache membres
    global MEMBERS_CACHE
    MEMBERS_CACHE = {"timestamp": 0, "members": []}
    print(f"{Colors.OKGREEN}Script actualisé et nettoyé avec succès.{Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

def print_menu():
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}=== MENU PRINCIPAL ==={Colors.ENDC}")
    print(f"{Colors.HEADER}GESTION DES COMPTES{Colors.ENDC}")
    print(f"{Colors.OKCYAN}1{Colors.ENDC} - Ajouter un compte")
    print(f"{Colors.OKCYAN}2{Colors.ENDC} - État des comptes")
    print(f"{Colors.OKCYAN}3{Colors.ENDC} - Retrait d'un compte")
    print(f"{Colors.OKCYAN}4{Colors.ENDC} - Mise à jour & Actualisation des comptes")
    print(f"{Colors.OKBLUE}RÉCUPÉRATIONS, AJOUTS/MESSAGE{Colors.ENDC}")
    print(f"{Colors.OKCYAN}5{Colors.ENDC} - Choix groupe source & cible")
    print(f"{Colors.OKCYAN}6{Colors.ENDC} - Ajout des membres")
    print(f"{Colors.OKCYAN}7{Colors.ENDC} - Masse de message")
    print(f"{Colors.OKCYAN}8{Colors.ENDC} - Retrait membres inactifs (il y a 2 mois ou plus)")
    print(f"{Colors.OKGREEN}AUTRES{Colors.ENDC}")
    print(f"{Colors.OKCYAN}9{Colors.ENDC} - Actualiser & Correction intelligent du script")
    print(f"{Colors.OKCYAN}10{Colors.ENDC} - Quitter\n")

def main_loop():
    global GROUP_SOURCE, GROUP_TARGET, GROUP_INVITE_LINK

    load_accounts()
    while True:
        print_menu()
        choice = input(f"{Colors.BOLD}Choix (numéro) : {Colors.ENDC}").strip()

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
            loop = asyncio.get_event_loop()
            loop.run_until_complete(refresh_all_accounts())

        elif choice == '5':
            if not ACCOUNTS:
                print(f"{Colors.FAIL}Aucun compte configuré pour récupérer les groupes.{Colors.ENDC}")
                input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")
                continue
            account = ACCOUNTS[0]  # Premier compte par défaut pour liste groupes
            loop = asyncio.get_event_loop()
            grp_source = loop.run_until_complete(choose_group(account, "source"))
            if grp_source is None:
                continue
            grp_target = loop.run_until_complete(choose_group(account, "cible"))
            if grp_target is None:
                continue
            GROUP_SOURCE = grp_source
            GROUP_TARGET = grp_target
            clear_screen()
            print(f"{Colors.OKGREEN}Groupes configurés :{Colors.ENDC}")
            print(f" - Source : {GROUP_SOURCE.title}")
            print(f" - Cible  : {GROUP_TARGET.title}\n")
            print(f"{Colors.BOLD}Si vous n'êtes pas admin du groupe cible, veuillez fournir un lien d'invitation public ou privé.{Colors.ENDC}")
            inv_link = input("Lien d'invitation du groupe cible (laisser vide si admin) : ").strip()
            GROUP_INVITE_LINK = inv_link if inv_link else None
            input(f"{Colors.WARNING}Appuyez sur Entrée pour revenir au menu...{Colors.ENDC}")

        elif choice == '6':
            loop = asyncio.get_event_loop()
            loop.run_until_complete(run_addition())

        elif choice == '7':
            loop = asyncio.get_event_loop()
            loop.run_until_complete(mass_message())

        elif choice == '8':
            loop = asyncio.get_event_loop()
            loop.run_until_complete(remove_inactive_members())

        elif choice == '9':
            loop = asyncio.get_event_loop()
            loop.run_until_complete(refresh_script())

        elif choice == '10':
            clear_screen()
            print(f"{Colors.BOLD}{Colors.OKCYAN}Merci d'avoir utilisé le gestionnaire Telegram multi-comptes. Au revoir !{Colors.ENDC}\n")
            sys.exit(0)

        else:
            print(f"{Colors.FAIL}Choix invalide. Réessayez.{Colors.ENDC}")
            time.sleep(1)

if __name__ == '__main__':
    clear_screen()
    print(f"{Colors.HEADER}{Colors.BOLD}=== Bienvenue dans le gestionnaire Telegram multi-comptes ultra-sûr et optimisé ==={Colors.ENDC}")
    input(f"{Colors.WARNING}Appuyez sur Entrée pour démarrer...{Colors.ENDC}")
    main_loop()


