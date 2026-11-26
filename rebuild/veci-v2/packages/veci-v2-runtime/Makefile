include $(TOPDIR)/rules.mk

PKG_NAME:=veci-v2-runtime
PKG_VERSION:=0.1
PKG_RELEASE:=25

include $(INCLUDE_DIR)/package.mk

define Package/veci-v2-runtime
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 authenticated exact-board management backend (development)
  DEPENDS:=+iw +we5927-lte +veci-wifi-guardian +rpcd +jsonfilter +swconfig +flock +fwtool +ucert
endef

define Build/Compile
endef

define Package/veci-v2-runtime/description
  Small read-only hardware health API for ZBT-WE5927-DSIM.
  No driver or modem state changes; cannot claim AP or Internet readiness
  without real evidence. Source-only until field acceptance.
endef

define Package/veci-v2-runtime/conffiles
/etc/veci2-update-policy
endef

define Package/veci-v2-runtime/install
	$(INSTALL_DIR) $(1)/etc
	$(INSTALL_CONF) ./update-policy.default $(1)/etc/veci2-update-policy
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_BIN) ./veci2-verify-image $(1)/usr/libexec/veci2-verify-image
	$(INSTALL_BIN) ./veci2-restore-check $(1)/usr/libexec/veci2-restore-check
	$(INSTALL_BIN) ./veci2-lte-policy $(1)/usr/libexec/rpcd/veci.v2.lte
	$(INSTALL_BIN) ./veci2-wifi $(1)/usr/libexec/rpcd/veci.v2.wifi
	$(INSTALL_BIN) ./veci2-wifi-activate $(1)/usr/libexec/veci2-wifi-activate
	$(INSTALL_BIN) ./veci2-dns $(1)/usr/libexec/rpcd/veci.v2.dns
	$(INSTALL_BIN) ./veci2-static-leases $(1)/usr/libexec/rpcd/veci.v2.dhcp
	$(INSTALL_DATA) ./veci2-lan-bounds $(1)/usr/libexec/veci2-lan-bounds
	$(INSTALL_BIN) ./veci2-sim-manual $(1)/usr/libexec/rpcd/veci.v2.sim
	$(INSTALL_BIN) ./veci2-firewall $(1)/usr/libexec/rpcd/veci.v2.firewall
	$(INSTALL_BIN) ./veci2-system-admin $(1)/usr/libexec/rpcd/veci.v2.system
	$(INSTALL_BIN) ./veci2-observe $(1)/usr/libexec/veci2-observe
	$(INSTALL_BIN) ./veci2-observe-rpc $(1)/usr/libexec/rpcd/veci.v2.observability
	$(INSTALL_DATA) ./veci2-observe-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-observability.json
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/veci2-observe $(1)/etc/init.d/veci2-observe
	$(INSTALL_DATA) ./veci2-wifi-controls $(1)/usr/libexec/veci2-wifi-controls
	$(INSTALL_BIN) ./veci2-cron $(1)/usr/libexec/rpcd/veci.v2.cron
	$(INSTALL_BIN) ./veci2-services $(1)/usr/libexec/rpcd/veci.v2.services
	$(INSTALL_DATA) ./veci2-cron.awk $(1)/usr/libexec/veci2-cron.awk
	$(INSTALL_DATA) ./veci2-services-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-services.json
	$(INSTALL_DATA) ./veci2-cron-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-cron.json
	$(INSTALL_BIN) ./veci2-gpio-watchdog $(1)/usr/libexec/veci2-gpio-watchdog
	$(INSTALL_BIN) ./veci2-watchdog-status $(1)/usr/libexec/rpcd/veci.v2.watchdog
	$(INSTALL_DATA) ./veci2-watchdog-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-watchdog.json
	$(INSTALL_BIN) ./veci2-guest-check $(1)/usr/libexec/rpcd/veci.v2.guest
	$(INSTALL_DATA) ./veci2-guest-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-guest.json
	$(INSTALL_BIN) ./veci2-update-policy $(1)/usr/libexec/rpcd/veci.v2.updatepolicy
	$(INSTALL_DATA) ./veci2-addon-profiles $(1)/usr/libexec/veci2-addon-profiles
	$(INSTALL_BIN) ./veci2-addon $(1)/usr/libexec/rpcd/veci.v2.addon
	$(INSTALL_DATA) ./veci2-addon-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-addon.json
	$(INSTALL_BIN) ./veci2-sim-lock $(1)/usr/libexec/rpcd/veci.v2.simlock
	$(INSTALL_BIN) ./veci2-status $(1)/usr/libexec/rpcd/veci.v2
	$(INSTALL_BIN) ./veci2-interfaces $(1)/usr/libexec/rpcd/veci.v2.interfaces
	$(INSTALL_BIN) ./veci2-routes $(1)/usr/libexec/rpcd/veci.v2.routes
	$(INSTALL_BIN) ./veci2-access $(1)/usr/libexec/rpcd/veci.v2.access
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./veci2-status-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-runtime.json
	$(INSTALL_DATA) ./veci2-access-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-access.json
	$(INSTALL_DATA) ./veci2-routes-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-routes.json
	$(INSTALL_DATA) ./veci2-interfaces-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-interfaces.json
endef

define Package/veci-v2-runtime/postinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] || /etc/init.d/veci2-observe enable >/dev/null 2>&1 || true
endef

$(eval $(call BuildPackage,veci-v2-runtime))
