const developmentRepositoryUrl = 'https://github.com/xinjiegit/UCLAMoonshot-math-verifier';

export const repositoryUrl =
  process.env.NEXT_PUBLIC_REPOSITORY_URL ||
  (process.env.NODE_ENV === 'development' ? developmentRepositoryUrl : '');

export const releaseDownloadUrl = repositoryUrl
  ? `${repositoryUrl}/releases/latest/download/math-verifier.zip`
  : '';
