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
const searchInput = document.querySelector('#search');
const summary = document.querySelector('#search-summary');
const results = document.querySelector('#results');
const dialog = document.querySelector('#edit-dialog');
const editForm = document.querySelector('#edit-form');
const editError = document.querySelector('#edit-error');
const saveButton = document.querySelector('#edit-save');
const cancelButton = document.querySelector('#edit-cancel');
let requestVersion = 0;
let searchTimer;
let editingCode;
let editTrigger;

async function load() {
  const version = ++requestVersion;
  const search = searchInput.value.trim();
  try {
    const data = await (await request(`/api/links?search=${encodeURIComponent(search)}`)).json();
    if (version !== requestVersion) return;
    render(data.items);
    if (notice.className === 'error') notice.textContent = '';
    notice.className = '';
    summary.textContent = data.items.length
      ? `${data.items.length} links shown.`
      : search ? 'No links match your search.' : 'No links yet.';
  } catch (error) {
    if (version !== requestVersion) return;
    notice.textContent = error.message;
    notice.className = 'error';
    summary.textContent = '';
    results.replaceChildren();
  }
}

function render(items) {
  results.replaceChildren();
  for (const item of items) {
    const row = document.createElement('li');
    const details = document.createElement('div');
    const alias = document.createElement('strong');
    alias.textContent = item.code;
    const destination = document.createElement('p');
    destination.textContent = item.destinationUrl;
    const meta = document.createElement('p');
    meta.className = 'link-meta';
    meta.textContent = [
      item.isActive ? 'Active' : 'Inactive',
      item.description,
      `${item.clickCount} new clicks`,
      `${item.historicalClickCount} historical clicks`
    ].filter(Boolean).join(' · ');
    details.append(alias, destination, meta);
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.textContent = 'Edit';
    edit.setAttribute('aria-label', `Edit ${item.code}`);
    edit.addEventListener('click', () => openEditor(item, edit));
    row.append(details, edit);
    results.append(row);
  }
}

function openEditor(item, trigger) {
  editingCode = item.code;
  editTrigger = trigger;
  document.querySelector('#edit-alias').textContent = item.shortUrl;
  for (const field of ['destinationUrl', 'description', 'tags']) {
    editForm.elements[field].value = item[field] ?? '';
  }
  editForm.elements.expiresOn.value = valueForDateInput(item.expiresOn);
  editForm.elements.isActive.checked = item.isActive;
  editError.textContent = '';
  dialog.showModal();
  editForm.elements.destinationUrl.focus();
}

cancelButton.addEventListener('click', () => dialog.close());
dialog.addEventListener('cancel', event => {
  if (saveButton.disabled) event.preventDefault();
});
dialog.addEventListener('close', () => editTrigger?.focus());
editForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (saveButton.disabled) return;
  const values = Object.fromEntries(new FormData(editForm));
  values.isActive = editForm.elements.isActive.checked;
  const code = editingCode.split('/').map(encodeURIComponent).join('/');
  saveButton.disabled = cancelButton.disabled = true;
  editError.textContent = '';
  try {
    await request(`/api/links/item/${code}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(values)
    });
    dialog.close();
    await load();
    const updated = [...results.querySelectorAll('button')]
      .find(button => button.getAttribute('aria-label') === `Edit ${editingCode}`);
    (updated || searchInput).focus();
  } catch (error) {
    editError.textContent = error.message;
  } finally {
    saveButton.disabled = cancelButton.disabled = false;
  }
});
document.querySelector('#create-form').addEventListener('submit',async e=>{e.preventDefault();try{const response=await request('/api/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});const item=await response.json();notice.className='';notice.textContent=`Created ${item.shortUrl}`;e.target.reset();load()}catch(err){notice.textContent=err.message;notice.className='error'}});
searchInput.addEventListener('input', () => {
  ++requestVersion;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(load, 250);
});
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
