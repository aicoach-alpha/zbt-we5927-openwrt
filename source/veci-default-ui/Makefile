include $(TOPDIR)/rules.mk

PKG_NAME:=veci-default-ui
PKG_RELEASE:=1

include $(INCLUDE_DIR)/package.mk

define Package/veci-default-ui
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=VeCI default landing page
  DEPENDS:=+veci +uhttpd
endef

define Package/veci-default-ui/description
 Makes VeCI the default web landing page while retaining LuCI under /cgi-bin/luci/.
 The change is reversible with /usr/sbin/veci-default-ui disable.
endef

define Package/veci-default-ui/conffiles
/etc/config/veci_default_ui
endef

define Build/Compile
endef

define Package/veci-default-ui/install
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/veci_default_ui $(1)/etc/config/veci_default_ui
	$(INSTALL_DIR) $(1)/usr/sbin
	$(INSTALL_BIN) ./files/usr/sbin/veci-default-ui $(1)/usr/sbin/veci-default-ui
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/98-veci-default-ui $(1)/etc/uci-defaults/98-veci-default-ui
endef

$(eval $(call BuildPackage,veci-default-ui))
