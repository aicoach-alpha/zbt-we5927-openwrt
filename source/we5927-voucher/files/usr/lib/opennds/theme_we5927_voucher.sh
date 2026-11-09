#!/bin/sh
# WE5927 voucher ThemeSpec for openNDS.
# Derived from the public openNDS ThemeSpec interface; project-specific code is GPL-2.0-only.

title='theme_we5927_voucher'

generate_splash_sequence() {
	credential_login
}

header() {
	gatewayurl=$(printf "${gatewayurl//%/\\x}")
	echo "<!DOCTYPE html>
<html>
<head>
<meta http-equiv=\"Cache-Control\" content=\"no-cache, no-store, must-revalidate\">
<meta http-equiv=\"Pragma\" content=\"no-cache\">
<meta http-equiv=\"Expires\" content=\"0\">
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
<link rel=\"stylesheet\" type=\"text/css\" href=\"$gatewayurl/splash.css\">
<title>WIFI-Alpha Guest</title>
</head>
<body>
<div class=\"offset\"><div class=\"insert\" style=\"max-width:100%;\">"
}

footer() {
	echo "<hr>
<div style=\"font-size:0.7em;\">WIFI-Alpha Guest Voucher Portal</div>
</div></div></body></html>"
	exit 0
}

login_form() {
	echo "<big-red>Guest Internet Access</big-red><br>
<med-blue>Enter the username and password printed on your voucher.</med-blue><br><hr>
<form action=\"/opennds_preauth/\" method=\"get\">
<input type=\"hidden\" name=\"fas\" value=\"$fas\">
<label>Username</label><br>
<input type=\"text\" name=\"username\" autocomplete=\"off\" required><br><br>
<label>Password</label><br>
<input type=\"password\" name=\"password\" autocomplete=\"off\" required><br><br>
<label><input type=\"checkbox\" name=\"tos\" value=\"accepted\" required> I agree to use this guest connection lawfully and responsibly.</label><br><br>
<input type=\"submit\" value=\"Connect\">
</form><br>
<small>Voucher credentials are temporary access credentials. Do not reuse a personal password here.</small>"
}

credential_login() {
	if [ "$tos" = 'accepted' ] && [ -n "$username" ] && [ -n "$password" ]; then
		credential_validation
		footer
	fi
	login_form
	footer
}

credential_validation() {
	result="$(/usr/sbin/we5927-voucher verify "$username" "$password" "$clientmac" 2>/dev/null)"
	status="$(printf '%s' "$result" | cut -d'|' -f1)"
	remaining="$(printf '%s' "$result" | cut -d'|' -f2)"

	if [ "$status" != 'VALID' ]; then
		echo "<big-red>Voucher is invalid, expired, disabled, or already bound to another device.</big-red><br><br>
<form action=\"$originurl\" method=\"get\"><input type=\"submit\" value=\"Try Again\"></form>"
		return 1
	fi

	echo "$remaining" | grep -Eq '^[0-9]+$' || return 1
	[ "$remaining" -gt 0 ] || return 1
	sessiontimeout="$remaining"
	upload_rate='0'
	download_rate='0'
	upload_quota='0'
	download_quota='0'
	quotas="$sessiontimeout $upload_rate $download_rate $upload_quota $download_quota"
	userinfo="$title - $username"

	auth_log

	if [ "$ndsstatus" = 'authenticated' ]; then
		originurl=$(printf "${originurl//%/\\x}")
		echo "<big-red>Connected.</big-red><br>
<med-blue>Voucher remaining time: $sessiontimeout minute(s).</med-blue><br><br>
<form><input type=\"button\" value=\"Continue\" onClick=\"location.href='$originurl'\"></form>"
	else
		echo "<big-red>Authentication could not be completed. Please try again.</big-red>"
	fi
}

sessiontimeout='0'
upload_rate='0'
download_rate='0'
upload_quota='0'
download_quota='0'
quotas="$sessiontimeout $upload_rate $download_rate $upload_quota $download_quota"

ndscustomparams=''
ndscustomimages=''
ndscustomfiles=''
ndsparamlist="$ndsparamlist $ndscustomparams $ndscustomimages $ndscustomfiles"
additionalthemevars='tos username password'
fasvarlist="$fasvarlist $additionalthemevars"
userinfo="$title"
