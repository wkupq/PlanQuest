/**
 * start-dev.js
 * react-scripts 5.x 의 allowedHosts 버그 우회 스크립트
 * dotenv 보다 먼저 환경변수를 설정해서 override 방지
 */
process.env.DANGEROUSLY_DISABLE_HOST_CHECK = 'true';
require('react-scripts/scripts/start');
