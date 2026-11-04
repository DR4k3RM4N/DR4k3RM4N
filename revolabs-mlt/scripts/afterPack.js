// Pone el icono y los datos de versión (Propiedades → Detalles) en el .exe de Windows
// sin necesitar Windows ni wine para compilar.
const fs = require('fs');
const path = require('path');

exports.default = async function afterPack(ctx) {
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
  const [maj, min, pat] = pkg.version.split('.').map(Number);
  vi.setFileVersion(maj, min, pat, 0, 1033);
  vi.setProductVersion(maj, min, pat, 0, 1033);
  const strings = {
    CompanyName: 'Revo Labs',
    FileDescription: 'RevoLabs MLT - Monitor de Lives de TikTok',
    ProductName: 'RevoLabs MLT',
    LegalCopyright: '© 2026 Revo Labs',
    OriginalFilename: 'RevoLabs MLT.exe',
    InternalName: 'RevoLabs MLT',
    FileVersion: pkg.version,
    ProductVersion: pkg.version,
  };
  for (const lng of vi.getAllLanguagesForStringValues()) vi.setStringValues(lng, strings);
  vi.outputToResourceEntries(res.entries);

  res.outputResource(exe);
  fs.writeFileSync(exePath, Buffer.from(exe.generate()));
};
