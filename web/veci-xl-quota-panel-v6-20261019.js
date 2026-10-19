// VeCI XL panel: display authenticated operator quotas only, never router traffic.
export async function mountXlConnection(root, api) {
 const host=root.querySelector('#veci-xl-connection'); if(!host) return;
 host.replaceChildren();
 const heading=document.createElement('strong'), message=document.createElement('p');
 const quota=document.createElement('div'), btn=document.createElement('button');
 const disconnect=document.createElement('button');
 btn.type='button';btn.className='button button-secondary';btn.textContent='Refresh Status XL';
 disconnect.type='button';disconnect.className='button button-secondary';disconnect.textContent='Putuskan Sesi XL';disconnect.hidden=true;
 host.append(heading,message,quota,btn,disconnect);
 const say=(a,b)=>{heading.textContent=a;message.textContent=b;};
 const bytes=v=>(v/1073741824).toFixed(2)+' GiB';
 const validBucket=b=>b&&typeof b.label==='string'&&b.label.length>0&&b.label.length<=100&&
    Number.isSafeInteger(b.remaining_bytes)&&b.remaining_bytes>=0&&
    (!Object.hasOwn(b,'total_bytes')||(Number.isSafeInteger(b.total_bytes)&&b.total_bytes>=b.remaining_bytes))&&
    (!Object.hasOwn(b,'expires_at')||(typeof b.expires_at==='string'&&!Number.isNaN(Date.parse(b.expires_at))));
 let busy=false;
 async function load(){
   if(busy)return;busy=true;btn.disabled=true;disconnect.disabled=true;quota.replaceChildren();
   say('Memeriksa koneksi XL…','Tidak meminta OTP atau menghubungi operator.');
   try{
     const s=await api.call('veci.xl','status',{}, {timeout:5000});
     if(!s||typeof s.session!=='string'||typeof s.https_only!=='boolean'||typeof s.operator_configured!=='boolean')
       throw Error('invalid_status');
     disconnect.hidden=s.session==='not_connected';
     if(!s.https_only){disconnect.hidden=true;say('XL: HTTPS diperlukan','Autentikasi dinonaktifkan sampai HTTPS tersedia.');return;}
     if(!s.operator_configured){say('XL: konfigurasi operator belum tersedia','Backend terpasang; autentikasi belum dapat digunakan.');return;}
     if(s.session!=='verified'){
       const map={pending_profile:'menunggu verifikasi profil',otp_requested:'menunggu OTP'};
       say('XL: '+(map[s.session]||'belum terhubung'),'Sisa kuota operator tidak tersedia sebelum akun terverifikasi.');return;
     }
     say('XL: akun terverifikasi','Memeriksa cache kuota operator yang sudah ada.');
     const q=await api.call('veci.quota','status',{}, {timeout:5000});
     // A stale or synthetic cache must never be shown as operator entitlement.
     const t=Date.parse(q&&q.fetched_at);
     const age=Date.now()-t;
     const cacheState=typeof q?.state==='string'?q.state:'unavailable';
     if(!q||(q.provider!=='xl'&&q.operator!=='xl')||q.source!=='operator'||q.state!=='ok'||
        !Array.isArray(q.buckets)||q.buckets.length<1||q.buckets.length>30||
        !Number.isFinite(age)||age<0||age>1800000||!q.buckets.every(validBucket)){
       const names={not_connected:'belum terhubung',authentication_required:'autentikasi diperlukan',pending_otp:'menunggu OTP',stale:'cache kedaluwarsa',unavailable:'data belum tersedia',rate_limited:'dibatasi sementara'};
       if(Number.isFinite(age)&&age>1800000&&q?.source==='operator'&&cacheState==='ok'){
         say('XL: cache kedaluwarsa','Data operator terlalu lama untuk ditampilkan. Tidak melakukan refresh operator otomatis.');
       } else {
         say('XL: '+(names[cacheState]||'kuota resmi belum tersedia'),'Tidak ada saldo operator terverifikasi yang dapat ditampilkan.');
       }
       return;
     }
     say('XL: kuota operator','Data cache dari akun terverifikasi · '+new Date(t).toLocaleString('id-ID'));
     const list=document.createElement('ul');
     for(const b of q.buckets){
       const li=document.createElement('li');
       li.textContent=b.label+': '+bytes(b.remaining_bytes)+
         (Number.isSafeInteger(b.total_bytes)?' / '+bytes(b.total_bytes):'')+
         (typeof b.expires_at==='string'?' · berlaku sampai '+new Date(b.expires_at).toLocaleDateString('id-ID'):'');
       list.append(li);
     }
     quota.append(list);
   }catch{
     say('XL: status tidak tersedia','Status akun atau cache kuota tidak dapat dibaca oleh sesi VeCI.');
   }finally{busy=false;btn.disabled=false;disconnect.disabled=false;}
 }
 btn.addEventListener('click',()=>{void load();});
 disconnect.addEventListener('click',async()=>{
   if(busy||!window.confirm('Putuskan sesi XL pada router ini dan hapus token serta cache kuota lokal?'))return;
   busy=true;btn.disabled=true;disconnect.disabled=true;quota.replaceChildren();
   say('Memutuskan sesi XL…','Hanya menghapus data sesi lokal; tidak mencabut token di server operator.');
   try{
     const result=await api.call('veci.xl','logout',{}, {timeout:8000});
     if(result?.ok!==true||result.state!=='not_connected')throw Error('logout_failed');
     say('XL: sesi lokal terputus','Token dan cache kuota lokal telah dihapus. Pengaturan aplikasi operator dipertahankan.');
     disconnect.hidden=true;
   }catch{
     say('XL: logout gagal','Status sesi belum dikonfirmasi terputus. Coba Refresh Status XL.');
   }finally{
     busy=false;btn.disabled=false;disconnect.disabled=false;
   }
 });
 await load();
}
