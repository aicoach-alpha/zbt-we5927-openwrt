include $(TOPDIR)/rules.mk

PKG_NAME:=veci-v2-runtime
PKG_VERSION:=0.1
PKG_RELEASE:=17

include $(INCLUDE_DIR)/package.mk

define Package/veci-v2-runtime
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI v2 read-only exact-board health provider (development)
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
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd $(1)/usr/share/rpcd/acl.d
	$(INSTALL_BIN) ./veci2-leds $(1)/usr/libexec/rpcd/veci.v2.leds
	$(INSTALL_DATA) ./veci2-leds-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-leds.json
	$(INSTALL_BIN) ./veci2-cron $(1)/usr/libexec/rpcd/veci.v2.cron
	$(INSTALL_DATA) ./veci2-cron.awk $(1)/usr/libexec/veci2-cron.awk
	$(INSTALL_DATA) ./veci2-cron-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-cron.json
	$(INSTALL_BIN) ./veci2-services $(1)/usr/libexec/rpcd/veci.v2.services
	$(INSTALL_DATA) ./veci2-services-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-services.json
	$(INSTALL_BIN) ./veci2-reliability $(1)/usr/libexec/veci2-reliability
	$(INSTALL_BIN) ./veci2-diagnostics $(1)/usr/libexec/rpcd/veci.v2.diag
	$(INSTALL_DATA) ./veci2-diag-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-diagnostics.json
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_DIR) $(1)/etc
	$(INSTALL_CONF) ./update-policy.default $(1)/etc/veci2-update-policy
	$(INSTALL_BIN) ./veci2-update-policy $(1)/usr/libexec/rpcd/veci.v2.updatepolicy
	$(INSTALL_BIN) ./veci2-verify-image $(1)/usr/libexec/veci2-verify-image
	$(INSTALL_DATA) ./veci2-lan-bounds $(1)/usr/libexec/veci2-lan-bounds
	$(INSTALL_BIN) ./veci2-firewall $(1)/usr/libexec/rpcd/veci.v2.firewall
	$(INSTALL_BIN) ./veci2-dhcp $(1)/usr/libexec/rpcd/veci.v2.dhcp
	$(INSTALL_BIN) ./veci2-lte-policy $(1)/usr/libexec/rpcd/veci.v2.lte
	$(INSTALL_BIN) ./veci2-sim-lock $(1)/usr/libexec/rpcd/veci.v2.simlock
	$(INSTALL_DATA) ./veci2-wifi-controls $(1)/usr/libexec/veci2-wifi-controls
	$(INSTALL_BIN) ./veci2-wifi $(1)/usr/libexec/rpcd/veci.v2.wifi
	$(INSTALL_BIN) ./veci2-status $(1)/usr/libexec/rpcd/veci.v2
	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_BIN) ./veci2-interfaces $(1)/usr/libexec/rpcd/veci.v2.interfaces
	$(INSTALL_DATA) ./veci2-interfaces-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-interfaces.json
	$(INSTALL_BIN) ./veci2-access $(1)/usr/libexec/rpcd/veci.v2.access
	$(INSTALL_DATA) ./veci2-access-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-access.json
	$(INSTALL_BIN) ./veci2-time $(1)/usr/libexec/rpcd/veci.v2.time
	$(INSTALL_DATA) ./veci2-time-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-time.json
	$(INSTALL_DATA) ./veci2-firewall-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-firewall.json
	$(INSTALL_DATA) ./veci2-dhcp-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-dhcp.json
	$(INSTALL_DATA) ./veci2-status-acl.json $(1)/usr/share/rpcd/acl.d/veci-v2-runtime.json
endef

$(eval $(call BuildPackage,veci-v2-runtime))
