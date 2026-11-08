<?php
/**
 * Plugin Name: AutoCanal – Conexión
 * Description: Deja que tu oficina AutoCanal publique en tu blog aunque tu hosting borre la cabecera de acceso o algún plugin revise al usuario antes de tiempo. No hay que tocar .htaccess. WordPress valida tu contraseña de aplicación con su propia función, igual que siempre.
 * Version: 1.3
 * Requires at least: 5.6
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

// 1) Si el hosting borró la cabecera Authorization, toma los mismos datos de la cabecera propia X-AutoCanal-Auth.
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

/**
 * 2) Si otro plugin preguntó por el usuario antes de que WordPress revisara las contraseñas de aplicación,
 * WordPress se queda con "visitante". Aquí, ya dentro de la API, se revisa la contraseña con la función de
 * WordPress (wp_authenticate_application_password) y, si es correcta, se entra con ese usuario.
 * Solo actúa cuando la petición trae la cabecera de la oficina (X-AutoCanal-Auth).
 */
function autocanal_entrar() {
	global $autocanal_estado;
	if ( null !== $autocanal_estado ) {
		return;
	}
	$autocanal_estado = '';
	if ( empty( $_SERVER['HTTP_X_AUTOCANAL_AUTH'] ) || get_current_user_id() > 0 ) {
		return;
	}
	$datos = base64_decode( wp_unslash( $_SERVER['HTTP_X_AUTOCANAL_AUTH'] ), true );
	if ( false === $datos || false === strpos( $datos, ':' ) || ! function_exists( 'wp_authenticate_application_password' ) ) {
		$autocanal_estado = 'sin_datos';
		return;
	}
	list( $usuario, $clave ) = explode( ':', $datos, 2 );
	$res = wp_authenticate_application_password( null, $usuario, $clave );
	if ( $res instanceof WP_User ) {
		wp_set_current_user( $res->ID );
		$autocanal_estado = 'entro';
	} elseif ( is_wp_error( $res ) ) {
		$autocanal_estado = $res->get_error_code();
	} else {
		$autocanal_estado = 'no_revisada';
	}
}
add_action( 'rest_api_init', 'autocanal_entrar', 1 );
add_filter( 'rest_pre_dispatch', function ( $resultado ) {
	autocanal_entrar();
	return $resultado;
}, 1 );

// Prueba para la oficina: dice si el plugin está activo y QUÉ pasa (solo sí/no y códigos, nunca valores).
add_action( 'rest_api_init', function () {
	register_rest_route( 'autocanal/v1', '/ping', array(
		'methods'             => 'GET',
		'permission_callback' => '__return_true',
		'callback'            => function () {
			global $autocanal_estado;
			$app = isset( $GLOBALS['wp_rest_application_password_status'] ) ? $GLOBALS['wp_rest_application_password_status'] : null;
			return array(
				'plugin'                 => '1.3',
				'llega_authorization'    => ! empty( $_SERVER['HTTP_AUTHORIZATION'] ) || ! empty( $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ),
				'llega_autocanal'        => ! empty( $_SERVER['HTTP_X_AUTOCANAL_AUTH'] ),
				'usuario_listo'          => ! empty( $_SERVER['PHP_AUTH_USER'] ),
				'contrasenas_aplicacion' => function_exists( 'wp_is_application_passwords_available' ) && wp_is_application_passwords_available(),
				'en_uso'                 => class_exists( 'WP_Application_Passwords' ) && WP_Application_Passwords::is_in_use(),
				'https'                  => is_ssl(),
				'reconocido'             => get_current_user_id() > 0,
				'error_contrasena'       => is_wp_error( $app ) ? $app->get_error_code() : '',
				'plugin_entro'           => (string) $autocanal_estado,
			);
		},
	) );
} );
