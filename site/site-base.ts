// Share the homepage URL and asset base for root and repository Pages sites.
const repositoryName = process.env.GITHUB_REPOSITORY?.split('/')[1];
const isUserSite = repositoryName?.endsWith('.github.io');

export const siteBasePath = repositoryName && !isUserSite ? `/${repositoryName}/` : '/';
