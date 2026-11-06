import process from 'node:process';

const { CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, DEPLOYMENT_ENVIRONMENT, GITHUB_SHA } = process.env;
if (!CLOUDFLARE_ACCOUNT_ID || !CLOUDFLARE_API_TOKEN || !GITHUB_SHA)
  throw new Error('Cloudflare account, token and config commit are required');
if (DEPLOYMENT_ENVIRONMENT !== 'production' && DEPLOYMENT_ENVIRONMENT !== 'staging')
  throw new Error('Select production or staging for Worker config publication');

const { checkConfigCompatibility, readWorkerConfig } = await import(process.argv[2]);
const snapshot = { ...(await readWorkerConfig('.')), commit: GITHUB_SHA };
const deployment = `zyploop-${DEPLOYMENT_ENVIRONMENT}`;

const request = async (path, { allowMissing = false, body, method = 'GET' } = {}) => {
  const response = await globalThis.fetch(
    `https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/${path}`,
    {
      body: JSON.stringify(body),
      headers: { Authorization: `Bearer ${CLOUDFLARE_API_TOKEN}`, 'Content-Type': 'application/json' },
      method,
      signal: globalThis.AbortSignal.timeout(30_000),
    },
  );
  if (allowMissing && response.status === 404) return;
  if (!response.ok) throw new Error(`Cloudflare ${method} ${path} returned HTTP ${response.status}`);
  return response.json();
};

const getResult = async (path, options) => {
  const response = await request(path, options);
  if (response === undefined) return;
  if (!response.success) throw new Error(`Cloudflare could not read ${path}`);
  return response.result;
};

const findNamespace = async title => {
  const pageSize = 50;
  for (let page = 1; ; page += 1) {
    const namespaces = await getResult(`storage/kv/namespaces?per_page=${pageSize}&page=${page}`);
    const namespace = namespaces.find(entry => entry.title === title);
    if (namespace) return namespace.id;
    if (namespaces.length < pageSize) throw new Error(`Provision the ${title} KV namespace before publishing`);
  }
};

const readSecretReference = (reference, label) => {
  const binding = /^\$\{([A-Z][A-Z0-9_]*)\}$/u.exec(reference)?.[1];
  if (!binding) throw new Error(`Worker config ${label} must use a Secrets Store reference`);
  return binding;
};
const directorySecrets = new Map(
  snapshot.identityProviders.map(provider => [
    provider.id,
    readSecretReference(provider.type === 'entra' ? provider.client_secret : provider.directory.token, provider.id),
  ]),
);
const workerSecrets = { email: [], identity: directorySecrets.values().toArray(), teams: [], widget: [] };
for (const connector of snapshot.connectors) {
  if (connector.type === 'msteams') workerSecrets.teams.push(directorySecrets.get(connector.identity_provider));
  if (connector.type === 'widget' && connector.turnstile)
    workerSecrets.widget.push(readSecretReference(connector.turnstile.secret_key, connector.id));
  if (connector.type === 'email')
    workerSecrets.email.push(
      readSecretReference(
        connector.provider === 'jmap' ? connector.jmap.token : connector.microsoft_graph.client_secret,
        connector.id,
      ),
    );
}

const namespace = await findNamespace(`${deployment}-config`);
const key = `storage/kv/namespaces/${namespace}/values/current`;
const published = await request(key, { allowMissing: true });
if (published?.revision === snapshot.revision) {
  globalThis.console.log(`Worker config ${snapshot.revision} is already published`);
} else {
  let emailWorker;
  for (const [kind, secrets] of Object.entries(workerSecrets)) {
    const script = `workers/scripts/${deployment}-${kind}`;
    const deployments = await getResult(`${script}/deployments`, { allowMissing: true });
    const versions = deployments?.deployments[0]?.versions ?? [];
    for (const { version_id: version } of versions) {
      const { resources } = await getResult(`${script}/versions/${version}`);
      const { bindings } = resources;
      if (bindings.every(binding => binding.name !== 'CONFIG' || binding.namespace_id !== namespace))
        throw new Error(`${deployment}-${kind} must use the ${deployment}-config KV namespace`);
      const validator = bindings.find(binding => binding.name === 'CONFIG_VALIDATOR_VERSION')?.text;
      if (!validator) throw new Error(`${deployment}-${kind} is missing its config validator version`);
      await checkConfigCompatibility('.', ['workers'], validator);
      const requiredSecrets = new Set(secrets);
      for (const secret of requiredSecrets) {
        if (
          bindings.every(
            binding => binding.name !== secret || binding.secret_name !== `${DEPLOYMENT_ENVIRONMENT}_${secret}`,
          )
        )
          throw new Error(`${deployment}-${kind} needs the ${secret} binding before publishing this config`);
      }
    }
    if (kind === 'email' && versions.length > 0) emailWorker = script;
  }
  if (emailWorker && published?.settings.email_maintenance_hours !== snapshot.settings.email_maintenance_hours) {
    const hours = snapshot.settings.email_maintenance_hours;
    const response = await request(`${emailWorker}/schedules`, {
      body: [{ cron: `0 ${hours === 24 ? '0' : `*/${hours}`} * * *` }],
      method: 'PUT',
    });
    if (!response.success) throw new Error('Cloudflare refused the Email Worker schedule');
  }
  const response = await request(key, { body: snapshot, method: 'PUT' });
  if (!response.success) throw new Error('Cloudflare refused Worker config publication');
  globalThis.console.log(
    `Published Worker config ${snapshot.revision} from ${snapshot.commit} to ${deployment}-config`,
  );
}
