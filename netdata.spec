%bcond_without systemd
#We use some plugins which need suid
%global  _hardened_build 1
# Build release candidate
%global upver        1.16.0
Name:                netdata
Version:             %{upver}%{?rcver:~%{rcver}}
Release:             2
Summary:             Real-time performance monitoring
License:             GPLv3 and GPLv3+ and ASL 2.0 and CC-BY and MIT and WTFPL
URL:                 https://github.com/%{name}/%{name}/
Source0:             https://github.com/%{name}/%{name}/archive/v%{upver}%{?rcver:-%{rcver}}/%{name}-%{upver}%{?rcver:-%{rcver}}.tar.gz
Source1:             netdata.tmpfiles.conf
Source2:             netdata.init
Source3:             netdata.conf
Patch0:              netdata-fix-shebang-1.16.0.patch
Patch1:		     netdata-fix-python2-not-compatible-with-python3.patch
# Remove embedded font
Patch10:             netdata-remove-fonts-1.12.0.patch
Patch11:             Fix-missing-extern-in-some-global-variables.patch
BuildRequires:       zlib-devel git autoconf automake pkgconfig libuuid-devel freeipmi-devel httpd
BuildRequires:       cppcheck gcc tinyxml2
Requires:            nodejs glyphicons-halflings-fonts
%if %{with systemd}
BuildRequires:       systemd
%{?systemd_requires}
%else
Requires:            initscripts /sbin/service /sbin/chkconfig
%endif
Requires:            %{name}-data = %{version}-%{release} %{name}-conf = %{version}-%{release}
%description
netdata is the fastest way to visualize metrics. It is a resource
efficient, highly optimized system for collecting and visualizing any
type of realtime time-series data, from CPU usage, disk activity, SQL
queries, API calls, web site visitors, etc.
netdata tries to visualize the truth of now, in its greatest detail,
so that you can get insights of what is happening now and what just
happened, on your systems and applications.

%package data
BuildArch:           noarch
Summary:             Data files for netdata
%description data
Data files for netdata

%package conf
BuildArch:           noarch
Summary:             Configuration files for netdata
%description conf
Configuration files for netdata

%package freeipmi
Summary:             FreeIPMI plugin for netdata
Requires:            %{name}%{?_isa} = %{version}-%{release}
License:             GPLv3
%description freeipmi
freeipmi plugin for netdata

%prep
%setup -qn %{name}-%{upver}%{?rcver:-%{rcver}}
%patch0 -p1
%patch1 -p1
# Remove embedded font(added in requires)
%patch10 -p1
%patch11 -p1
rm -rf web/fonts

%build
autoreconf -ivf
%configure \
    --prefix=%{_prefix} \
    --sysconfdir=%{_sysconfdir} \
    --localstatedir=%{_localstatedir} \
    --enable-plugin-freeipmi \
    --with-zlib --with-math --with-user=netdata
%make_build

%install
%make_install
find %{buildroot} -name '.keep' -delete
# Unit file
%if %{with systemd}
mkdir -p %{buildroot}%{_unitdir}
mkdir -p %{buildroot}%{_tmpfilesdir}
install -Dp -m 0644 system/netdata.service %{buildroot}%{_unitdir}/%{name}.service
install -p -m 0644 %{SOURCE1} %{buildroot}%{_tmpfilesdir}/%{name}.conf
%else
# Init script
mkdir -p %{buildroot}%{_initrddir}
install -p -Dp -m 0755 %{SOURCE2} %{buildroot}%{_initrddir}/%{name}
%endif
mkdir -p %{buildroot}%{_localstatedir}/lib/%{name}
mkdir -p %{buildroot}%{_sysconfdir}/logrotate.d
install -p -m 0644 %{SOURCE3} %{buildroot}%{_sysconfdir}/%{name}/
install -p -m 0644 system/netdata.logrotate %{buildroot}%{_sysconfdir}/logrotate.d/%{name}
# Conf files must be in /etc, dixit FHS
mv %{buildroot}%{_libdir}/%{name}/conf.d %{buildroot}%{_sysconfdir}/%{name}/
# Scripts must not be in /etc
mv %{buildroot}%{_sysconfdir}/%{name}/edit-config %{buildroot}%{_libexecdir}/%{name}/edit-config
# Fix EOL
sed -i -e 's/\r//' %{buildroot}%{_datadir}/%{name}/web/lib/tableExport-1.6.0.min.js
# Delete useless hidden dir
rm -rf %{buildroot}%{_datadir}/%{name}/web/.well-known

%check
./cppcheck.sh

%pre
getent group netdata > /dev/null || groupadd -r netdata
getent passwd netdata > /dev/null || useradd -r -g netdata -c "NetData User" -s /sbin/nologin -d /var/log/%{name} netdata

%post
%if 0%{?systemd_post:1}
%systemd_post %{name}.service
%else
if [ $1 = 1 ]; then
    # Initial installation
%if %{with systemd}
    /bin/systemctl daemon-reload >/dev/null 2>&1 || :
%else
    /sbin/chkconfig --add %{name}
%endif
fi
%endif
echo "The current config file can be downloaded with the following command"
echo "curl -o /etc/netdata/netdata.conf http://localhost:19999/netdata.conf"

%preun
%if 0%{?systemd_preun:1}
%systemd_preun %{name}.service
%else
if [ "$1" = 0 ] ; then
    # Package removal, not upgrade
%if %{with systemd}
    /bin/systemctl --no-reload disable %{name}.service >/dev/null 2>&1 || :
    /bin/systemctl stop %{name}.service >/dev/null 2>&1 || :
%else
    /sbin/service %{name} stop > /dev/null 2>&1
    /sbin/chkconfig --del %{name}
%endif
fi
exit 0
%endif

%postun
%if 0%{?systemd_postun_with_restart:1}
%systemd_postun_with_restart %{name}.service
%else
%if %{with systemd}
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ]; then
# Package upgrade, not uninstall
    /bin/systemctl try-restart %{name}.service >/dev/null 2>&1 || :
fi
%else
if [ "$1" -ge 1 ]; then
    /sbin/service %{name} restart > /dev/null 2>&1
fi
exit 0
%endif
%endif
%triggerun -- netdata
%if %{with systemd}
if [ -f /etc/rc.d/init.d/%{name} ]; then
# Save the current service runlevel info
# User must manually run systemd-sysv-convert --apply netdata
# to migrate them to systemd targets
/usr/bin/systemd-sysv-convert --save %{name} >/dev/null 2>&1 ||:
# Run these because the SysV package being removed won't do them
/sbin/chkconfig --del %{name} >/dev/null 2>&1 || :
/bin/systemctl try-restart %{name}.service >/dev/null 2>&1 || :
fi
%endif

%files
%doc README.md CHANGELOG.md CODE_OF_CONDUCT.md CONTRIBUTORS.md HISTORICAL_CHANGELOG.md
%license LICENSE REDISTRIBUTED.md
%{_sbindir}/%{name}
%{_libexecdir}/%{name}
%if %{with systemd}
%{_unitdir}/%{name}.service
%{_tmpfilesdir}/%{name}.conf
%else
%attr(0755,root,root) %{_initrddir}/%{name}
%endif
%attr(4755,root,root) %{_libexecdir}/%{name}/plugins.d/apps.plugin
%exclude %{_libexecdir}/%{name}/plugins.d/freeipmi.plugin
%attr(0755, netdata, netdata) %{_localstatedir}/lib/%{name}
%attr(0755, netdata, netdata) %dir %{_localstatedir}/cache/%{name}
%attr(0755, netdata, netdata) %dir %{_localstatedir}/log/%{name}
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}

%files conf
%doc README.md
%license LICENSE REDISTRIBUTED.md
%dir %{_sysconfdir}/%{name}
%dir %{_sysconfdir}/%{name}/conf.d
%dir %{_sysconfdir}/%{name}/conf.d/charts.d
%dir %{_sysconfdir}/%{name}/conf.d/health.d
%dir %{_sysconfdir}/%{name}/conf.d/python.d
%dir %{_sysconfdir}/%{name}/conf.d/statsd.d
%config(noreplace) %{_sysconfdir}/%{name}/%{name}.conf
%config(noreplace) %{_sysconfdir}/%{name}/conf.d/*.conf
%config(noreplace) %{_sysconfdir}/%{name}/conf.d/charts.d/*.conf
%config(noreplace) %{_sysconfdir}/%{name}/conf.d/health.d/*.conf
%config(noreplace) %{_sysconfdir}/%{name}/conf.d/python.d/*.conf
%config(noreplace) %{_sysconfdir}/%{name}/conf.d/statsd.d/*.conf

%files data
%doc README.md
%license LICENSE REDISTRIBUTED.md
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/web

%files freeipmi
%doc README.md
%license LICENSE REDISTRIBUTED.md
%attr(4755,root,root) %{_libexecdir}/%{name}/plugins.d/freeipmi.plugin

%changelog
* Wed Aug 04 2021 sunguoshuai <sunguoshuai@huawei.com> - 1.16.0 - 2
- Fix missing extern in some global variables

* Thu Jun 24 2021 baizhonggui <baizhonggui@huawei.com> - 1.16.0 - 1
- package init
