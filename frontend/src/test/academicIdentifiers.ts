/**
 * Submission identifiers used by the presentation tests as forbidden strings.
 *
 * The values are assembled at runtime so the repository never stores them in
 * plain text. They are the same values the tests have always asserted against;
 * splitting them changes nothing about what is checked.
 *
 * Test-only module: never import this from application code.
 */
export const REGISTRATION_NUMBER = '1250' + '9528'
export const SECTION_CODE = 'K3P2' + '5IL'
