# List or edit standard five-field records while preserving unmanaged lines.
function field_valid(s, lo, hi,  n,i,a,m,b,k,c) {
  n=split(s,a,",")
  if (!n) return 0
  for (i=1;i<=n;i++) {
    m=split(a[i],b,"/")
    if (m<1 || m>2 || (m==2 && (b[2]!~/^[1-9][0-9]?$/ || b[2]>hi-lo+1))) return 0
    if (b[1]=="*") continue
    k=split(b[1],c,"-")
    if (k<1 || k>2 || c[1]!~/^[0-9][0-9]?$/ || c[1]+0<lo || c[1]+0>hi) return 0
    if (k==2 && (c[2]!~/^[0-9][0-9]?$/ || c[2]+0<c[1]+0 || c[2]+0>hi)) return 0
  }
  return 1
}
function valid(s, a) {
  return split(s,a," ")==5 && field_valid(a[1],0,59) && field_valid(a[2],0,23) &&
    field_valid(a[3],1,31) && field_valid(a[4],1,12) && field_valid(a[5],0,6)
}
BEGIN {
  marker="# VeCI paused: "
  if ((mode=="save" || mode=="add" || mode=="setReboot") && !valid(schedule)) { invalid=1; exit 2 }
}
{
  original=$0
  record=original
  enabled=index(record,marker)!=1
  if (!enabled) record=substr(record,length(marker)+1)
  sub(/^[ \t]+/,"",record)
  remaining=record
  old=""
  for (i=1;i<=5;i++) {
    if (!match(remaining,/^[^ \t]+[ \t]+/)) break
    token=substr(remaining,1,RLENGTH)
    remaining=substr(remaining,RLENGTH+1)
    sub(/[ \t]+$/,"",token)
    old=old (i==1?"":" ") token
  }
  supported=valid(old) && length(remaining)>0
  owned=(remaining=="/sbin/reboot # VeCI managed autoreboot")
  if (owned) {
    owned_count++
    if (!supported || split(old,fields," ")!=5 || fields[1]!~/^[0-9][0-9]?$/ || fields[2]!~/^[0-9][0-9]?$/ || fields[3]!="*" || fields[4]!="*" || fields[5]!~/^[0-6](,[0-6])*$/) owned_invalid=1
    reboot_enabled=enabled; reboot_minute=fields[1]+0; reboot_hour=fields[2]+0; reboot_days=fields[5]
    if(mode=="setReboot" || mode=="rebootstate") next
    # Dedicated API only: ordinary cron editing cannot enable this reboot.
    if(mode=="list") next
    if(mode=="save" || mode=="remove"){if(NR==row)exit 2;print original;next}
  }
  if(mode=="rebootstate") next
  if(mode=="setReboot"){print original;next}
  if (mode=="list" && supported) {
    command=remaining
    sub(/[ \t].*$/,"",command)
    sub(/^.*\//,"",command)
    if (command!~/^[A-Za-z0-9_.-]+$/) command="job"
    if (remaining=="/bin/busybox uptime | /bin/busybox logger -t veci-cron-uptime") command="uptime"
    if (remaining=="/bin/busybox free | /bin/busybox logger -t veci-cron-memory") command="memory"
    print NR "\t" enabled "\t" old "\t" command
  }
  if (mode!="list") {
    if (mode!="add" && NR==row && supported) {
      if (mode=="save") print (active=="1"?"":marker) schedule " " remaining
      changed=1
    } else print original
  }
}
END {
  if(mode=="rebootstate" || mode=="setReboot"){
    if(invalid || owned_count>1 || owned_invalid)exit 2
    if(mode=="rebootstate"){
      if(!owned_count) print "0\t0\t3\t0,1,2,3,4,5,6"
      else print reboot_enabled "\t" reboot_minute "\t" reboot_hour "\t" reboot_days
    }else print (active=="1"?"":marker) schedule " /sbin/reboot # VeCI managed autoreboot"
  }
  if (mode=="add" && !invalid) print (active=="1"?"":marker) schedule " " cmd
  if ((mode=="save" || mode=="remove") && !changed) exit 2
}
