import pymysql, subprocess, argparse, shutil, os, sys, zipfile, requests, re, datetime, time
from sys import platform
from pathlib import Path

#Example Tor Browser target directory:
#   A:\\Tor' 'Browser' 'x64\\Tor' 'Browser
#   //mnt//a//Tor' 'Browser' 'x64//Tor' 'Browser 

#Args
parser = argparse.ArgumentParser()

parser.add_argument("-g","--gpg", action="store_true", help="Download gpg windows installer to cwd")

#Command to reference backups
parser.add_argument("-t","--date", type=str, help="Reference a backup by date")

#Commands for a backup's directory/compression
parser.add_argument("-d","--directory", type=str, help="Target directory you want to encrypt & backup")
parser.add_argument("-c","--compression", type=int, help="Specify the level of compression you want")

#Commands for MySql user/password
parser.add_argument("-u","--user", type=str, help="Username for MySQL")
parser.add_argument("-p","--password", type=str, help="Password for MySQL")

#Command to decrypt backup
parser.add_argument("-dec","--decrypt", action="store_true", help="Decrypt a backup")

#Mutually Exclusive
group = parser.add_mutually_exclusive_group()
group.add_argument("-a","--add", action="store_true", help="Add a new backup to the database & backups directory")
group.add_argument("-r","--remove", action="store_true", help="Remove a backup from the database & backups directory")

args = parser.parse_args()

dir = args.directory
db = "torsync"
tb = "backups"

#Get the current date
currdate = "-" + str(datetime.datetime.today().strftime('%Y-%m-%d'))

def create_db(user, password):
	dbconn = pymysql.connect("localhost", user, password)
	cursor = dbconn.cursor()
	#create pycryption database
	cursor.execute("CREATE DATABASE IF NOT EXISTS " + db)
	dbconn.commit()
	cursor.close()

def create_tb(user, password):
	dbconn = pymysql.connect("localhost", user, password)
	cursor = dbconn.cursor()
	#create backups table
	#create table fields & rows. Filename (15), date (char 10), Filetype (char 10), Filesize (int)
	cursor.execute("""CREATE TABLE IF NOT EXISTS """ + db + """.""" + tb + """ (
		Filename  VARCHAR(15),
		Date  VARCHAR(15),
		Filetype  VARCHAR(10),
		Filesize  INT
	)""")
	dbconn.commit()
	cursor.close()

def insert_tb(user, password, filename, date, filetype, filesize):
	dbconn = pymysql.connect("localhost", user, password, db = db)
	cursor = dbconn.cursor()
	insert = "INSERT INTO " + tb + " (Filename, Date, Filetype, Filesize) VALUES (\"{}\", \"{}\", \"{}\", \"{}\");".format(filename, date, filetype, str(filesize))
	check = "SELECT * FROM " + tb + ";"
	cursor.execute(insert)
	cursor.execute(check)
	rows = cursor.fetchall()
	for row in rows:
		print(row)
	dbconn.commit()
	cursor.close()

def remove_tb(user, password, date):
	dbconn = pymysql.connect("localhost", user, password, db = db)
	cursor = dbconn.cursor()
	delete = "DELETE FROM " + tb + " WHERE Date = '-" + date + "';"
	cursor.execute(delete)
	dbconn.commit()
	cursor.close()
	
def select_row(user, password, date):
	dbconn = pymysql.connect("localhost", user, password, db = db)
	cursor = dbconn.cursor()
	select = "SELECT * FROM " + tb + " WHERE Date = '-" + date + "';"
	cursor.execute(select)
	fields = cursor.fetchone()
	select_row.row = (fields[0] + fields[1] + fields[2])
	dbconn.commit()
	cursor.close()

#Download gpg installer to cwd
if args.gpg and sys.platform == "win32":

	html = requests.get("https://www.gnupg.org/download/")

	#Request has been successful
	if html.status_code == 200:

		html = requests.get("https://www.gnupg.org/download/").text
		ftp = re.search(r'\bftp\b/\bgcrypt/\bbinary/\bgnupg\b-\bw32-\d+.\d+.\d+_\d+.\bexe\b', html).group()
		filename = re.search(r'\bgnupg\b-\bw32-\d+.\d+.\d+_\d+.\bexe\b', html).group()
		url = "https://www.gnupg.org/" + ftp
		dwnld = requests.get(url)

		#Download latest GnuPG for w32
		request = open(filename, 'wb').write(dwnld.content)

	else:
		print("Could not find download url! Exiting...")
		sys.exit()

elif args.gpg and sys.platform == "linux":
	
	print("GnuPG comes installed on linux!")
	sys.exit()

elif args.gpg and sys.platform == "darwin":
	
	html = requests.get("https://sourceforge.net/p/gpgosx/docu/Download/")

	if html.status_code == 200:

		html = requests.get("https://sourceforge.net/p/gpgosx/docu/Download/").text
		ftp = re.search(r'\bprojects\b/\bgpgosx\b/\bfiles\b/\bGnuPG.\d+.\d+.\d+.\bdmg\b/\bdownload\b', html).group()
		filename = re.search(r'\bGnuPG.\d+.\d+.\d+.\bdmg\b/\bdownload\b', html).group()
		url = "https://sourceforge.net/" + ftp
		dwnld = requests.get(url)

		#Download GPG DMG for MacOS
		request = open(filename, 'wb').write(dwnld.content)

	else:
		print("Could not find download url! Exiting...")
		sys.exit()

#Add new backup to database using directory + compression arg
elif args.add and args.directory and args.user and args.password:
	print("Adding a new backup!")

	create_db(args.user, args.password)
	create_tb(args.user, args.password)

	bkdir = os.getcwd() + "/backups/Tor-Browser" + currdate

	#Handle duplicate files and folders
	if os.path.isdir(bkdir) == True:
		shutil.rmtree(bkdir)
	try:
		dir = shutil.copytree(dir, bkdir)
	except IOError as e:
		print("Cannot copy directory! Exiting...")
		shutil.rmtree(bkdir)
		sys.exit()

	#Zip file
	zip_file = dir + '.zip'

	#GPG file
	gpg_file = zip_file + '.gpg'

	if os.path.isfile(zip_file) == True:
		print("Found duplicate backup zip! Removing...")
		os.remove(zip_file)
	
	if os.path.isfile(gpg_file) == True:
		print("Found duplicate encrypted backup zip! Removing...")
		os.remove(gpg_file)

	print("zip_name: " + zip_file)

	#Zip up entire target directory
	def zip_directory(zip_file, dir):
		print("Zipping the target directory...")
		zip = zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED, compresslevel = 9)

		for dirname, subdirs, files in os.walk(dir):
			zip.write(dirname)
			for filename in files:
					zip.write(os.path.join(dirname, filename))

		print("Tor Browser backup zipped successfully!")
		zip.close()

	#Encrypt file using GPG
	def aes_encrypt(zip_file):
		
		#GPG --- C:\Users\Alex>gpg --sign --passphrase --symmetric --cipher-algo AES256 C:\Users\Alex\Desktop\pycryption\Tor-Browser-2018-11-23.zip
		print("Encrypting the zip file...")
		proc = subprocess.Popen(['gpg', '--sign', '--passphrase', '--symmetric', '--cipher-algo', 'AES256', zip_file])
		proc.communicate()[0]
		proc.returncode
		if proc == 1:
			proc.terminate()
			sys.exit()
		print("Encryption successful!")
	
	zip_directory(zip_file, dir)
	aes_encrypt(zip_file)
	os.remove(zip_file)
	shutil.rmtree(bkdir)

	#Get the size of the gpg file in MB
	try:
		size = os.path.getsize(gpg_file)
		filesize = (size >> 20)
	except FileNotFoundError as e:
		print("Encrypted zip file could not be found!\n   Exiting...")
		sys.exit()
	
	#Extract the gpg file name from the full path
	filename = re.search(r'\bTor\b-\bBrowser\b', gpg_file).group()
	filetype = re.search(r'.\bzip\b.\bgpg\b', gpg_file).group()

	#Get the GPG file
	print(filesize)
	insert_tb(args.user, args.password, filename, currdate, filetype, filesize)
	
	#Exit when finished
	sys.exit()

elif args.remove and args.user and args.password and args.date:
	print("Removing backup!")
	date = args.date
	if bool(re.match(r'\d+-\d+-\d+', date)) == True:
		dir = os.getcwd() + "/backups/"
		os.chdir(dir)
		full_path = dir + "Tor-Browser-" + date + ".zip.gpg"
		part_path = dir + "Tor-Browser-" + date + ".zip"
		folder = dir + "Tor-Browser-" + date
		try:
			shutil.rmtree(folder)
			os.remove(str(part_path)
			os.remove(str(full_path))
			remove_tb(args.user, args.password, args.date)
		except IOError as e:
			print("File does not exist in backups directory!\n   Exiting...")
			sys.exit()
	else:
		print("""Please provide arguments correctly!
	Example (1):
	   --gpg
	Example (2):
	   --add --directory A:\\Your\\target\\directory --compression (1-9) --user 'your_mysql_username' --password 'your_mysql_password'
	Example (3):
	   --remove --user 'your_mysql_username' --password 'your_mysql_password' --date YYYY-MM-DD
	Example (4):
	   --decrypt --user 'your_mysql_username' --password 'your_mysql_password' --date YYYY-MM-DD
	Exiting...""")
	sys.exit()

elif args.decrypt and args.user and args.password and args.date:

	select_row(args.user, args.password, args.date)

	#Call row from outside select_row function
	backup = select_row.row
	backups = os.getcwd() + "/backups/" + backup

	#C:\Users\Alex\Desktop\TorSync/backups/Tor-Browser-2018-12-30.zip.gpg
	zip_name = re.search(r'\bTor\b-\bBrowser\b-\d+-\d+-\d+.\bzip\b',backups).group()
	zip = os.getcwd() + "/backups/" + zip_name

	if os.path.isfile(backups):
		def aes_decrypt(zip_file,enc_file):
			print("Decrypting the zip file...")
			proc = subprocess.Popen(['gpg','--output',zip_file,'--decrypt',enc_file])
			proc.communicate()[0]
			proc.returncode
			if proc == 1:
				proc.terminate()
				sys.exit()
			print("Decryption Successful!")
		aes_decrypt(zip,backups)
	else:
		print("Could not find file specified!\n   Exiting...")
		sys.exit()

else:
	print("""Please provide arguments correctly!
	Example (1):
	   --gpg
	Example (2):
	   --add --directory A:\\Your\\target\\directory --compression (1-9) --user 'your_mysql_username' --password 'your_mysql_password'
	Example (3):
	   --remove --user 'your_mysql_username' --password 'your_mysql_password' --date YYYY-MM-DD
	Example (4):
	   --decrypt --user 'your_mysql_username' --password 'your_mysql_password' --date YYYY-MM-DD
	Exiting...""")
	sys.exit()