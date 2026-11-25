const notice = document.querySelector('#notice');
async function showSession() {
  const status = document.querySelector('#account-status');
  const signIn = document.querySelector('#sign-in');
  const signOut = document.querySelector('#sign-out');
  try {
    const response = await fetch('/api/links?session=1', {cache: 'no-store'});
    if (response.status === 401 || response.status === 403) {
      status.textContent = 'Sign in with your Sujeeth Foundation account.';
      signIn.hidden = false;
      return;
    }
    if (!response.ok) throw new Error('Unable to check sign-in.');
    const session = await response.json();
    status.textContent = `Signed in as ${session.name}`;
    signOut.hidden = false;
  } catch (error) {
    status.textContent = 'Unable to check sign-in. Refresh to try again.';
    signIn.hidden = false;
  }
}
const request = async (url, options = {}) => {
  const response = await fetch(url, options);
  if (response.status === 401) throw new Error('Sign in with your Sujeeth Foundation account.');
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || `Request failed (${response.status})`); }
  return response;
};
const valueForDateInput = value => value ? value.replace('Z','').slice(0,16) : '';
async function load() {
  const search = document.querySelector('#search').value;
  try { const data = await (await request(`/api/links?search=${encodeURIComponent(search)}`)).json(); render(data.items); notice.textContent = `${data.items.length} links shown.`; }
  catch (error) { notice.textContent = error.message; notice.className='error'; document.querySelector('#results').replaceChildren(); }
}
function render(items) {
  const target = document.querySelector('#results'); target.replaceChildren();
  for (const item of items) { const form = document.querySelector('#edit-template').content.firstElementChild.cloneNode(true); form.querySelector('h3').textContent = item.shortUrl; form.destinationUrl.value=item.destinationUrl; form.description.value=item.description; form.tags.value=item.tags; form.expiresOn.value=valueForDateInput(item.expiresOn); form.isActive.checked=item.isActive; const meta=document.createElement('p');meta.className='link-meta';meta.textContent=`${item.clickCount} new clicks · ${item.historicalClickCount} historical clicks · ${item.source}`;form.insertBefore(meta,form.firstChild.nextSibling); form.addEventListener('submit', async e => {e.preventDefault();const values=Object.fromEntries(new FormData(form));values.isActive=form.isActive.checked;try {await request(`/api/links/item/${item.code.split('/').map(encodeURIComponent).join('/')}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});notice.textContent='Changes saved.';load()}catch(err){notice.textContent=err.message;notice.className='error'}});target.append(form); }
}
document.querySelector('#create-form').addEventListener('submit',async e=>{e.preventDefault();try{const response=await request('/api/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});const item=await response.json();notice.textContent=`Created ${item.shortUrl}`;e.target.reset();load()}catch(err){notice.textContent=err.message;notice.className='error'}});
document.querySelector('#search').addEventListener('input',()=>{clearTimeout(window.searchTimer);window.searchTimer=setTimeout(load,250)});
document.querySelector('#export').addEventListener('click',()=>window.location='/api/links/export');
document.querySelector('#import-form').addEventListener('submit', async e => {
  e.preventDefault();
  const file = document.querySelector('#import').files[0];
  if (!file) return;
  const target = document.querySelector('#import-report');
  const button = document.querySelector('#import-submit');
  target.replaceChildren();
  target.textContent = 'Importing links…';
  button.disabled = true;
  try {
    const response = await request('/api/links/import', {method:'POST', headers:{'Content-Type':'text/csv; charset=utf-8'}, body:await file.text()});
    const report = await response.json();
    target.replaceChildren();
    const summary = document.createElement('p');
    summary.textContent = `Imported ${report.imported.length}. Skipped ${report.conflicts.length} existing and ${report.invalid.length} invalid rows.`;
    target.append(summary);
    if (report.conflicts.length || report.invalid.length) {
      const list = document.createElement('ul');
      for (const row of report.conflicts) {
        const item = document.createElement('li'); item.textContent = `Row ${row.line}: alias ${row.code} already exists.`; list.append(item);
      }
      for (const row of report.invalid) {
        const item = document.createElement('li'); item.textContent = `Row ${row.line}: ${row.error}`; list.append(item);
      }
      target.append(list);
    }
    e.target.reset();
    await load();
  } catch (err) {
    target.textContent = `${err.message} Some rows may already have been imported. Check the link list before retrying; existing aliases will be skipped.`;
    await load();
  } finally { button.disabled = false; }
});
showSession();
load();
