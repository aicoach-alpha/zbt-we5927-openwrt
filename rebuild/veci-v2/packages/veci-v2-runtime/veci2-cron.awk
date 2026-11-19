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
  if (mode=="edit" && !valid(schedule)) exit 2
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
  if (mode=="list" && supported) {
    command=remaining
    sub(/[ \t].*$/,"",command)
    sub(/^.*\//,"",command)
    if (command!~/^[A-Za-z0-9_.-]+$/) command="job"
    print NR "\t" enabled "\t" old "\t" command
  }
  if (mode=="edit") {
    if (NR==row && supported) {
      print (active=="1"?"":marker) schedule " " remaining
      changed=1
    } else print original
  }
}
END { if (mode=="edit" && !changed) exit 2 }
