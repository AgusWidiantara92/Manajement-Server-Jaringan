import os
import subprocess
import string
import random
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext
import logging
import asyncio
import nest_asyncio
import pwd

nest_asyncio.apply()

SSH_CONFIG_FILE = "/etc/ssh/sshd_config"
AUTHORIZED_KEYS_DIR = "/home/{}/.ssh/authorized_keys"  # Lokasi file authorized_keys per pengguna

# Fungsi untuk memperbarui konfigurasi AllowUsers atau DenyUsers
def update_ssh_config(option, users):
    try:
        with open(SSH_CONFIG_FILE, "r") as file:
            lines = file.readlines()

        # Variabel untuk menentukan apakah baris sudah diubah
        updated = False

        # Cari atau ubah konfigurasi AllowUsers / DenyUsers
        for i, line in enumerate(lines):
            if line.strip().startswith(option):
                lines[i] = f"{option} {users}\n"
                updated = True
                break

        # Jika tidak ada entri, tambahkan konfigurasi baru
        if not updated:
            lines.append(f"{option} {users}\n")

        # Menulis kembali konfigurasi yang sudah diubah ke file
        with open(SSH_CONFIG_FILE, "w") as file:
            file.writelines(lines)

        # Restart SSH service untuk menerapkan perubahan
        subprocess.run(["sudo", "systemctl", "restart", "ssh"], check=True)
        return f"{option} updated with users: {users}. SSH service restarted."

    except Exception as e:
        return f"Error updating SSH config: {e}"

# Fungsi untuk menambahkan user ke konfigurasi SSH
def add_to_ssh_config(option, users):
    try:
        SSH_CONFIG_FILE = "/etc/ssh/sshd_config"

        # Pastikan users adalah list, jika belum
        if isinstance(users, str):
            users = [users]

        # Mengubah list pengguna menjadi string dengan spasi
        users_str = " ".join(users)

        # Membaca file konfigurasi SSH
        with open(SSH_CONFIG_FILE, "r") as file:
            lines = file.readlines()

        # Cari entri dan perbarui atau tambahkan
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(option):
                lines[i] = f"{option} {users_str}\n"
                updated = True
                break

        if not updated:
            lines.append(f"{option} {users_str}\n")

        # Menulis perubahan kembali ke file konfigurasi
        with open(SSH_CONFIG_FILE, "w") as file:
            file.writelines(lines)

        # Restart SSH service untuk menerapkan perubahan
        subprocess.run(["sudo", "systemctl", "restart", "ssh"], check=True)
        return f"User(s) added to {option}. SSH service restarted."

    except Exception as e:
        return f"Error adding users to SSH config: {e}"

# Fungsi untuk menghapus user dari konfigurasi SSH
def remove_user_from_ssh_config(option, users):
    try:
        SSH_CONFIG_FILE = "/etc/ssh/sshd_config"

        # Pastikan users adalah list, jika belum
        if isinstance(users, str):
            users = [users]

        # Membaca file konfigurasi SSH
        with open(SSH_CONFIG_FILE, "r") as file:
            lines = file.readlines()

        # Cari entri dan hapus user
        for i, line in enumerate(lines):
            if line.strip().startswith(option):
                existing_users = line.strip().split(" ")[1:]  # Mengambil daftar pengguna
                updated_users = [user for user in existing_users if user not in users]

                # Menulis kembali entri dengan pengguna yang diperbarui
                if updated_users:
                    lines[i] = f"{option} {' '.join(updated_users)}\n"
                else:
                    # Jika tidak ada pengguna yang tersisa, menambahkan komentar pada baris tersebut
                    lines[i] = f"# {option} {' '.join(existing_users)}\n"

                break

        # Menulis perubahan kembali ke file konfigurasi
        with open(SSH_CONFIG_FILE, "w") as file:
            file.writelines(lines)

        # Restart SSH service untuk menerapkan perubahan
        subprocess.run(["sudo", "systemctl", "restart", "ssh"], check=True)
        return f"User(s) removed from {option}. SSH service restarted."

    except Exception as e:
        return f"Error removing users from SSH config: {e}"

# Mengaktifkan logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fungsi untuk membuat password acak
def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))

# Fungsi untuk menampilkan daftar user di sistem
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Menggunakan subprocess untuk menjalankan perintah 'getent passwd'
        # yang menampilkan semua user
        result = subprocess.check_output("getent passwd", shell=True, text=True)
        users = result.splitlines()

        # Mengambil hanya nama user (kolom pertama) dari setiap baris
        valid_users = [user.split(":")[0] for user in users if "/bin/bash" in user or "/bin/sh" in user]

        if not valid_users:
            response = "No users with valid login shells found."
        else:
            response = "\n".join(valid_users)  # Menampilkan seluruh daftar user valid

        await update.message.reply_text(f"List of users:\n{response}")
    except Exception as e:
        logger.error(f"Error in list_users: {e}")
        await update.message.reply_text("Error fetching user list.")

# Fungsi untuk menambah user baru dengan password acak
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        username = context.args[0] if context.args else None
        if not username:
            await update.message.reply_text("Usage: /add_user <username>")
            return

        # Periksa apakah user sudah ada
        result = subprocess.run(['id', '-u', username], capture_output=True, text=True)
        if result.returncode == 0:
            await update.message.reply_text(f"User '{username}' already exists.")
            return

        # Menambahkan user baru
        subprocess.run(['sudo', 'useradd', '--no-user-group', '-m', '-s', '/bin/bash', username])

        # Membuat password acak
        password = generate_random_password()

        # Menggunakan 'chpasswd' untuk mengatur password user
        subprocess.run(f"echo '{username}:{password}' | sudo chpasswd", shell=True)

        # Mengirim password kepada pengguna
        await update.message.reply_text(
            f"User '{username}' has been added successfully.\n"
            f"Generated password: `{password}`\n"
            f"**Please store this password securely!**"
        )
    except Exception as e:
        logger.error(f"Error in add_user: {e}")
        await update.message.reply_text("Error adding user.")


# Fungsi untuk menghapus user
async def del_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        username = context.args[0] if context.args else None
        if not username:
            await update.message.reply_text("Usage: /del_user <username>")
            return

        # Periksa apakah user ada sebelum mencoba menghapus
        result = subprocess.run(['id', '-u', username], capture_output=True, text=True)
        if result.returncode != 0:
            await update.message.reply_text(f"User '{username}' does not exist.")
            return

        # Menghapus user dan direktori home-nya
        subprocess.run(['sudo', 'userdel', '-r', username], check=True)

        # Konfirmasi penghapusan
        await update.message.reply_text(f"User '{username}' has been deleted along with their home directory.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in del_user: {e}")
        await update.message.reply_text(
            f"Failed to delete user '{username}'. Please ensure the user exists and try again."
        )
    except Exception as e:
        logger.error(f"Error in del_user: {e}")
        await update.message.reply_text("An unexpected error occurred while deleting the user.")

# Fungsi untuk melihat pengguna yang ada dalam AllowUsers dan DenyUsers
async def list_deny_allow_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        allow_users = []
        deny_users = []

        # Membaca file sshd_config
        with open(SSH_CONFIG_FILE, "r") as file:
            lines = file.readlines()

        # Memeriksa entri AllowUsers dan DenyUsers
        allow_found = False
        deny_found = False

        for line in lines:
            line = line.strip()
            if line.startswith("AllowUsers"):
                allow_found = True
                allow_users = line.split()[1:]  # Ambil setelah AllowUsers
            elif line.startswith("DenyUsers"):
                deny_found = True
                deny_users = line.split()[1:]  # Ambil setelah DenyUsers

        # Menyusun hasil untuk balasan
        result = "Authentication settings for users:\n"

        # Menampilkan pengguna yang diizinkan
        if allow_found:
            result += "- AllowUsers:\n"
            result += "\n".join(f"  {user}" for user in allow_users) + "\n"
        else:
            result += "- AllowUsers: not set\n"

        # Menampilkan pengguna yang dilarang
        if deny_found:
            result += "- DenyUsers:\n"
            result += "\n".join(f"  {user}" for user in deny_users) + "\n"
        else:
            result += "- DenyUsers: not set\n"

        await update.message.reply_text(result)

    except Exception as e:
        logger.error(f"Error in list_users: {e}")
        await update.message.reply_text("Error retrieving user settings.")


# Fungsi untuk menambah pengguna ke AllowUsers
async def add_to_allow_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        users = " ".join(context.args) if context.args else None
        if not users:
            await update.message.reply_text("Usage: /add_to_allow_users <user1> <user2> ...")
            return
        result = update_ssh_config("AllowUsers", users)
        await update.message.reply_text(result)
    except Exception as e:
        logger.error(f"Error in add_to_allow_users: {e}")
        await update.message.reply_text("Error updating AllowUsers configuration.")

# Fungsi untuk menambah pengguna ke DenyUsers
async def add_to_deny_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        users = " ".join(context.args) if context.args else None
        if not users:
            await update.message.reply_text("Usage: /add_to_deny_users <user1> <user2> ...")
            return
        result = update_ssh_config("DenyUsers", users)
        await update.message.reply_text(result)
    except Exception as e:
        logger.error(f"Error in add_to_deny_users: {e}")
        await update.message.reply_text("Error updating DenyUsers configuration.")

# Fungsi untuk menghapus pengguna dari AllowUsers
async def remove_from_allow_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        users = " ".join(context.args) if context.args else None
        if not users:
            await update.message.reply_text("Usage: /remove_from_allow_users <user1> <user2> ...")
            return
        result = remove_user_from_ssh_config("AllowUsers", users)
        await update.message.reply_text(result)
    except Exception as e:
        logger.error(f"Error in remove_from_allow_users: {e}")
        await update.message.reply_text("Error removing users from AllowUsers configuration.")

# Fungsi untuk menghapus pengguna dari DenyUsers
async def remove_from_deny_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        users = " ".join(context.args) if context.args else None
        if not users:
            await update.message.reply_text("Usage: /remove_from_deny_users <user1> <user2> ...")
            return
        result = remove_user_from_ssh_config("DenyUsers", users)
        await update.message.reply_text(result)
    except Exception as e:
        logger.error(f"Error in remove_from_deny_users: {e}")
        await update.message.reply_text("Error removing users from DenyUsers configuration.")


# Fungsi untuk menampilkan daftar grup
async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Menggunakan getent group untuk mendapatkan daftar grup
        result = subprocess.check_output("getent group", shell=True, text=True)
        groups = result.splitlines()

        # Hanya menampilkan nama grup
        group_names = [line.split(':')[0] for line in groups]

        # Ambil semua grup terakhir
        reonse = "\n".join(group_names)  # Ambil semua grup terakhir
        if not response:
            response = "No groups found."
        await update.message.reply_text(f"Last 10 groups:\n{response}")
    except Exception as e:
        logger.error(f"Error in list_groups: {e}")
        await update.message.reply_text("Error fetching group list.")

# Fungsi untuk menambah grup baru
async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        groupname = context.args[0] if context.args else None
        if not groupname:
            await update.message.reply_text("Usage: /add_group <groupname>")
            return

        subprocess.run(['sudo', 'groupadd', groupname])
        await update.message.reply_text(f"Group '{groupname}' has been added.")
    except Exception as e:
        logger.error(f"Error in add_group: {e}")
        await update.message.reply_text("Error adding group.")

async def del_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Memeriksa apakah nama grup diberikan
        groupname = context.args[0] if context.args else None
        if not groupname:
            await update.message.reply_text("Usage: /del_group <groupname>")
            return

        # Menjalankan perintah penghapusan grup
        subprocess.run(['sudo', 'groupdel', groupname], check=True)

        # Verifikasi apakah grup benar-benar dihapus
        result = subprocess.run(['getent', 'group', groupname], capture_output=True, text=True)
        if result.returncode != 0:  # Grup tidak ditemukan
            await update.message.reply_text(f"Group '{groupname}' has been deleted.")
        else:
            await update.message.reply_text(f"Group '{groupname}' could not be deleted. Please try again.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in del_group: {e}")
        await update.message.reply_text(f"Failed to delete group '{groupname}': {e}")
    except Exception as e:
        logger.error(f"Error in del_group: {e}")
        await update.message.reply_text(f"An unexpected error occurred: {e}")

# Fungsi untuk menambahkan user ke grup
async def add_user_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /add_to_group <username> <groupname>")
            return

        username = context.args[0]
        groupname = context.args[1]

        subprocess.run(['sudo', 'usermod', '-aG', groupname, username], check=True)

        await update.message.reply_text( 
            f"User '{username}' has been successfully added to the group '{groupname}'."
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Error in add_user_to_group: {e}")
        await update.message.reply_text(
            "Failed to add user to group. Please ensure the user and group exist and try again."
        )
    except Exception as e:
        logger.error(f"Error in add_user_to_group: {e}")
        await update.message.reply_text("An unexpected error occurred.")

async def remove_user_from_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /remove_from_group <username> <groupname>")
            return
        
        username = context.args[0]
        groupname = context.args[1]

        logger.info(f"Attempting to remove user '{username}' from group '{groupname}'...")
        result = subprocess.run(
            ['sudo', 'gpasswd', '-d', username, groupname],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            await update.message.reply_text(
                f"User '{username}' has been successfully removed from group '{groupname}'."
            )
        else:
            error_message = result.stderr.strip()
            await update.message.reply_text(
                f"Failed to remove user '{username}' from group '{groupname}':\n{error_message}"
            )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text("An unexpected error occurred while removing user from group.")


# Fungsi untuk menampilkan daftar user dalam grup tertentu
async def group_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        groupname = context.args[0] if context.args else None
        if not groupname:
            await update.message.reply_text("Usage: /group_members <groupname>")
            return

        # Mendapatkan informasi grup menggunakan getent group
        result = subprocess.check_output(f"getent group {groupname}", shell=True, text=True)

        # Format hasil: groupname:x:gid:user1,user2,...
        group_info = result.strip().split(":")

        if len(group_info) < 4 or not group_info[3]:  # Jika tidak ada anggota
            await update.message.reply_text(f"No members found in group '{groupname}'.")
            return 
        members = group_info[3].split(",")  # Memisahkan daftar anggota
        response = "\n".join(members)  # Format daftar anggota untuk ditampilkan
        await update.message.reply_text(f"Members of group '{groupname}':\n{response}")
    except subprocess.CalledProcessError:
        await update.message.reply_text(f"Group '{groupname}' not found.")
    except Exception as e:
        logger.error(f"Error in group_members: {e}")
        await update.message.reply_text("Error fetching group members.")

async def list_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        with open(SSH_CONFIG_FILE, "r") as file:
            lines = file.readlines()

        auth_status = {}
        current_user = None

        for line in lines:
            stripped_line = line.strip()

            # Mendeteksi blok "Match User"
            if stripped_line.startswith("Match User"):
                current_user = stripped_line.split(" ")[-1]
                if current_user not in auth_status:
                    auth_status[current_user] = {
                        "PasswordAuthentication": "not set",
                        "PubkeyAuthentication": "not set"
                    }

            # Memproses konfigurasi PasswordAuthentication
            elif current_user and "PasswordAuthentication" in stripped_line:
                if not stripped_line.startswith("#"):  # Abaikan baris yang dikomentari
                    auth_status[current_user]["PasswordAuthentication"] = stripped_line.split()[-1]

            # Memproses konfigurasi PubkeyAuthentication
            elif current_user and "PubkeyAuthentication" in stripped_line:
                if not stripped_line.startswith("#"):  # Abaikan baris yang dikomentari
                    auth_status[current_user]["PubkeyAuthentication"] = stripped_line.split()[-1]

        # Menyusun hasil dalam format yang diinginkan
        result = "Authentication settings per user:\n"
        for user, settings in auth_status.items():
            result += f"- {user}:\n"
            result += f"  PasswordAuthentication: {settings['PasswordAuthentication']}\n"
            result += f"  PubkeyAuthentication: {settings['PubkeyAuthentication']}\n"

        await update.message.reply_text(result)

    except Exception as e:
        logger.error(f"Error in list_auth: {e}")
        await update.message.reply_text("An error occurred while listing authentication settings.")

# Fungsi untuk mengatur Password Authentication untuk pengguna tertentu
async def set_password_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Mengecek apakah perintah diberikan dengan format yang benar
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /set_password_auth <username> <yes|no>")
            return

        username = context.args[0]
        value = context.args[1]

        # Mengecek validitas nilai (hanya 'yes' atau 'no' yang diterima)
        if value not in ["yes", "no"]:
            await update.message.reply_text("Value must be 'yes' or 'no'.")
            return

        # Membaca file sshd_config dan mencari entri untuk user tertentu
        with open(SSH_CONFIG_FILE, "r") as file:
            lines = file.readlines()

        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"Match User {username}"):
                # Mencari baris konfigurasi PasswordAuthentication
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("PasswordAuthentication"):
                        # Mengomentari baris sebelumnya
                        lines[j] = f"# {lines[j]}"  # Menambahkan # di awal baris untuk mengomentari
                        lines.insert(j + 1, f" PasswordAuthentication {value}\n")  # Menambahkan baris baru
                        updated = True
                        break
                if not updated:
                    # Jika tidak ditemukan, tambahkan baris baru
                    lines.insert(i + 1, f" PasswordAuthentication {value}\n")
                break

        if not updated:
            # Jika tidak ditemukan entri 'Match User <username>', tambahkan konfigurasi
            lines.append(f"Match User {username}\n")
            lines.append(f" PasswordAuthentication {value}\n")

        # Menulis kembali konfigurasi yang telah diperbarui
        with open(SSH_CONFIG_FILE, "w") as file:
            file.writelines(lines)

        # Restart SSH untuk menerapkan perubahan
        subprocess.run(["sudo", "systemctl", "restart", "ssh"], check=True)

        await update.message.reply_text(f"Password authentication for user '{username}' is set to '{value}'.")

    except Exception as e:
        logger.error(f"Error in set_password_auth: {e}")
        await update.message.reply_text("An error occurred while updating password authentication.")

# Fungsi untuk mengatur Public Key Authentication untuk pengguna tertentu
async def set_pubkey_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Mengecek apakah perintah diberikan dengan format yang benar
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /set_pubkey_auth <username> <yes|no>")
            return

        username = context.args[0]
        value = context.args[1]

        # Mengecek validitas nilai (hanya 'yes' atau 'no' yang diterima)
        if value not in ["yes", "no"]:
            await update.message.reply_text("Value must be 'yes' or 'no'.")
            return

        # Membaca file sshd_config dan mencari entri untuk user tertentu
        with open(SSH_CONFIG_FILE, "r") as file:
            lines = file.readlines()

        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"Match User {username}"):
                # Mencari baris konfigurasi PubkeyAuthentication
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("PubkeyAuthentication"):
                        # Mengomentari baris konfigurasi sebelumnya
                        lines[j] = f"# {lines[j]}"  # Mengomentari baris sebelumnya
                        # Menambahkan baris baru dengan nilai yang diinginkan
                        lines.insert(j + 1, f"    PubkeyAuthentication {value}\n")
                        updated = True
                        break
                break  # Keluar setelah menemukan user yang sesuai

        if not updated:
            # Jika entri 'Match User <username>' tidak ditemukan, tambahkan konfigurasi baru untuk user tersebut
            lines.append(f"Match User {username}\n")
            lines.append(f"    PubkeyAuthentication {value}\n")

        # Menulis kembali konfigurasi yang telah diperbarui
        with open(SSH_CONFIG_FILE, "w") as file:
            file.writelines(lines)

        # Restart SSH untuk menerapkan perubahan
        subprocess.run(["sudo", "systemctl", "restart", "ssh"], check=True)

        await update.message.reply_text(f"Pubkey authentication for user '{username}' is set to '{value}'.")

    except Exception as e:
        logger.error(f"Error in set_pubkey_auth: {e}")
        await update.message.reply_text("An error occurred while updating pubkey authentication.")

#fungsi untuk menampilkan pengguna yang login
async def list_logged_in_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Mengecek apakah pengguna mengirimkan argumen yang tidak perlu
        if len(context.args) > 0:
            await update.message.reply_text("Usage: /list_logged_in_users\nTidak perlu menambahkan argumen.")
            return

        # Menjalankan perintah `who` untuk mendapatkan daftar pengguna
        result = subprocess.run(["who"], stdout=subprocess.PIPE, text=True, check=True)
        output = result.stdout.strip()
        
        if output:
            await update.message.reply_text(f"Logged-in users:\n\n{output}")
        else:
            await update.message.reply_text("No users are currently logged in.")
    except Exception as e:
        await update.message.reply_text("An error occurred while fetching the logged-in users.")
        logger.error(f"Error in list_logged_in_users: {e}")


async def view_user_details(update, context):
    # Mengecek apakah username diberikan
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /view_user_details <username>")
        return

    username = context.args[0]

    # Mengecek apakah user ada di sistem
    try:
        user_info = pwd.getpwnam(username)
    except KeyError:
        await update.message.reply_text(f"User '{username}' tidak ditemukan di sistem.")
        return

    # Mengambil informasi user menggunakan 'id' command
    try:
        id_output = subprocess.check_output(["id", username], text=True)
    except subprocess.CalledProcessError:
        await update.message.reply_text(f"Gagal mendapatkan informasi untuk user '{username}'.")
        return

    # Informasi tambahan dari /etc/passwd
    user_details = f"""
    **Detail User: {username}**
    - UID: {user_info.pw_uid}
    - GID: {user_info.pw_gid}
    - Home Directory: {user_info.pw_dir}
    - Shell: {user_info.pw_shell}
    - Full Name: {user_info.pw_gecos}

    **Output 'id' Command:**
    {id_output.strip()}
    """
    await update.message.reply_text(user_details, parse_mode="Markdown")

    # Fungsi untuk mengubah nama grup
async def rename_group(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /rename_group <old_group> <new_group>")
        return

    old_group = context.args[0]
    new_group = context.args[1]

    # Mengecek apakah grup lama ada
    try:
        # Menjalankan perintah 'groupmod' untuk mengganti nama grup
        result = subprocess.run(
            ['sudo', 'groupmod', '-n', new_group, old_group],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await update.message.reply_text(f"Group {old_group} berhasil diganti menjadi {new_group}.")
    except subprocess.CalledProcessError as e:
        # Jika terjadi error, kirim pesan error
        await update.message.reply_text(f"Error: {str(e)}")

# Fungsi untuk menampilkan daftar perintah bot
async def set_bot_commands(application):
    commands = [
        BotCommand("help", "Get the list of commands"),
        BotCommand("start", "Start the bot")
    ]
    await application.bot.set_my_commands(commands)



# Fungsi untuk menampilkan daftar perintah ketika /help atau /daftar dipanggil
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Here are the available commands:\n"
        "/list_users - List users on the system\n"
        "/add_user - Add a new user\n"
        "/del_user - Delete a user\n"
	"/list_deny_allow_users - list member of deny and allow users\n"
	"/add_to_allow_users - Allow the user to log in\n"
	"/add_to_deny_users - Restrict the user from logging in\n"
	"/remove_from_allow_users - Delete user from AllowUser\n"
	"/remove_from_deny_users - Delete user from DenyUser\n"
        "/list_groups - List groups on the system\n"
        "/add_group - Add a new group\n"
        "/del_group - Delete a group\n"
        "/group_members - List members of a group\n"
        "/add_to_group - Add a member to groups\n"
	"/remove_from_group - delete user from group\n"
    "/rename_group - To rename group\n"
	"/list_auth - List member of pubkey & password auth\n"
        "/set_password_auth - Set password authentication for user\n"
        "/set_pubkey_auth - Set public key authentication for user\n"
        "/list_logged_in_users - To see who login in server\n"
        "/view_user_details - To see detail user\n"
    )

# Fungsi untuk menangani perintah /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to the Linux Admin Bot!\n"
        "Use /help to get the list of available commands."
    )

async def main() -> None:
    token = '7476982769:AAHh_HevYqpyWAn5ZtHvWA4-1V-W3zqSCaY'  # Ganti dengan token bot Anda
    application = Application.builder().token(token).build()

    # Menambahkan handler untuk perintah
    application.add_handler(CommandHandler("list_users", list_users))
    application.add_handler(CommandHandler("add_user", add_user))
    application.add_handler(CommandHandler("del_user", del_user))
    application.add_handler(CommandHandler("list_deny_allow_users", list_deny_allow_users))
    application.add_handler(CommandHandler("add_to_allow_users", add_to_allow_users))
    application.add_handler(CommandHandler("add_to_deny_users", add_to_deny_users))
    application.add_handler(CommandHandler("remove_from_allow_users", remove_from_allow_users))
    application.add_handler(CommandHandler("remove_from_deny_users", remove_from_deny_users))
    application.add_handler(CommandHandler("list_groups", list_groups))
    application.add_handler(CommandHandler("add_group", add_group))
    application.add_handler(CommandHandler("del_group", del_group))
    application.add_handler(CommandHandler("add_to_group", add_user_to_group))
    application.add_handler(CommandHandler("group_members", group_members))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("remove_from_group", remove_user_from_group))
    application.add_handler(CommandHandler("list_auth", list_auth))
    application.add_handler(CommandHandler("set_password_auth", set_password_auth))
    application.add_handler(CommandHandler("set_pubkey_auth", set_pubkey_auth))
    application.add_handler(CommandHandler("list_logged_in_users", list_logged_in_users))
    application.add_handler(CommandHandler("view_user_details", view_user_details))
    application.add_handler(CommandHandler("rename_group", rename_group))

    # Set daftar perintah bot
    await set_bot_commands(application)

    # Set daftar perintah bot
    await application.run_polling()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
