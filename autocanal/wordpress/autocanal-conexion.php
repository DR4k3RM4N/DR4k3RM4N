<?php
/**
 * Plugin Name: AutoCanal – Conexión
 * Description: Deja que tu oficina AutoCanal publique en tu blog aunque tu hosting borre la cabecera de acceso (Authorization). No hay que tocar .htaccess. WordPress sigue revisando tu contraseña de aplicación igual que siempre.
 * Version: 1.1
 * Requires at least: 5.6
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// Si el hosting borró la cabecera Authorization, toma los mismos datos de la cabecera propia X-AutoCanal-Auth.
// Solo los pone donde WordPress los busca; la contraseña de aplicación se valida igual que siempre.
if ( empty( $_SERVER['PHP_AUTH_USER'] ) && empty( $_SERVER['HTTP_AUTHORIZATION'] )
	&& empty( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ) && ! empty( $_SERVER['HTTP_X_AUTOCANAL_AUTH'] ) ) {
	$autocanal_datos = base64_decode( wp_unslash( $_SERVER['HTTP_X_AUTOCANAL_AUTH'] ), true );
	if ( false !== $autocanal_datos && false !== strpos( $autocanal_datos, ':' ) ) {
		list( $autocanal_usuario, $autocanal_clave ) = explode( ':', $autocanal_datos, 2 );
		$_SERVER['PHP_AUTH_USER'] = $autocanal_usuario;
		$_SERVER['PHP_AUTH_PW']   = $autocanal_clave;
	}
	unset( $autocanal_datos, $autocanal_usuario, $autocanal_clave );
}

// Prueba para la oficina: dice si el plugin está activo y QUÉ llega (solo sí/no, nunca los valores).
add_action( 'rest_api_init', function () {
	register_rest_route( 'autocanal/v1', '/ping', array(
		'methods'             => 'GET',
		'permission_callback' => '__return_true',
		'callback'            => function () {
			return array(
				'plugin'                 => '1.1',
				'llega_authorization'    => ! empty( $_SERVER['HTTP_AUTHORIZATION'] ) || ! empty( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ),
				'llega_autocanal'        => ! empty( $_SERVER['HTTP_X_AUTOCANAL_AUTH'] ),
				'usuario_listo'          => ! empty( $_SERVER['PHP_AUTH_USER'] ),
				'contrasenas_aplicacion' => function_exists( 'wp_is_application_passwords_available' ) && wp_is_application_passwords_available(),
				'https'                  => is_ssl(),
			);
		},
	) );
} );
