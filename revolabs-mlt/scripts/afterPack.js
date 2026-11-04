// Pone el icono y los datos de versión (Propiedades → Detalles) en el .exe de Windows
// sin necesitar Windows ni wine para compilar.
const fs = require('fs');
const path = require('path');

exports.default = async function afterPack(ctx) {
  if (ctx.electronPlatformName === 'darwin') return adhocSignMac(ctx);
  if (ctx.electronPlatformName !== 'win32') return;
  const ResEdit = await import('resedit');
  const { NtExecutable, NtExecutableResource, Resource, Data } = ResEdit;
  const pkg = require('../package.json');
  const exePath = path.join(ctx.appOutDir, `${ctx.packager.appInfo.productFilename}.exe`);
  const icoPath = path.join(ctx.packager.info.projectDir, 'build', 'icon.ico');

  const exe = NtExecutable.from(fs.readFileSync(exePath), { ignoreCert: true });
  const res = NtExecutableResource.from(exe);

  const iconFile = Data.IconFile.from(fs.readFileSync(icoPath));
  const groups = Resource.IconGroupEntry.fromEntries(res.entries);
  const groupId = groups.length ? groups[0].id : 1;
  const lang = groups.length ? groups[0].lang : 1033;
  Resource.IconGroupEntry.replaceIconsForResource(res.entries, groupId, lang, iconFile.icons.map((i) => i.data));

  const [vi] = Resource.VersionInfo.fromEntries(res.entries);
  // "0.5.2-1" se muestra como 0.5.2.1
  const [maj, min, pat, rev = 0] = pkg.version.match(/\d+/g).map(Number);
  const shown = [maj, min, pat].concat(rev ? [rev] : []).join('.');
  vi.setFileVersion(maj, min, pat, rev, 1033);
  vi.setProductVersion(maj, min, pat, rev, 1033);
  const strings = {
    CompanyName: 'Revo Labs',
    FileDescription: 'RevoLabs MLT - Monitor de Lives de TikTok',
    ProductName: 'RevoLabs MLT',
    LegalCopyright: '© 2026 Revo Labs',
    OriginalFilename: 'RevoLabs MLT.exe',
    InternalName: 'RevoLabs MLT',
    FileVersion: shown,
    ProductVersion: shown,
  };
  for (const lng of vi.getAllLanguagesForStringValues()) vi.setStringValues(lng, strings);
  vi.outputToResourceEntries(res.entries);

  res.outputResource(exe);
  fs.writeFileSync(exePath, Buffer.from(exe.generate()));
};

// En Mac con chip Apple (M1–M4) una app sin ninguna firma no abre ("está dañada").
// Cuando se compila en una Mac, se le pone una firma local (ad-hoc), que es gratis.
function adhocSignMac(ctx) {
  if (process.platform !== 'darwin') return;
  const { execFileSync } = require('child_process');
  const appPath = path.join(ctx.appOutDir, `${ctx.packager.appInfo.productFilename}.app`);
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', appPath], { stdio: 'inherit' });
}
