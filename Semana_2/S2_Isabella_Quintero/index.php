<html>
    <head>
        <title>Pagina Principal</title> <!-- formalidades -->
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>        
    </head>
    <body>  <!-- contenido visible de la pagina -->
    <!-- bg-dark es para el color de fondo de la barra de navegacion, navbar-dark es para el color del texto de la barra de navegacion -->
        <nav class="navbar navbar-expand-sm bg-success navbar-dark">     <!--Navbar - es la barra de navegacion-->
            <div class="container-fluid">
                <a class="navbar-brand" href="index.php">Logo</a> <!-- boton de logo que redirige a la pagina principal -->
                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                    <span class="navbar-toggler-icon"></span>
                </button> 
                <div class="collapse navbar-collapse" id="collapsibleNavbar"> <!-- collapse navbar-collapse es para que la barra de navegacion se colapse en pantallas pequeñas -->
                    <ul class="navbar-nav"> <!-- se crea otra barra y se agreganlos botones de la barra de navegacion -->
                        <li class="nav-item dropdown"> <!-- boton con menu desplegable -->
                            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Empresa</a>
                            <ul class="dropdown-menu">
                                <li><a class="dropdown-item" href="empresa.php">Quienes Somos</a></li> <!-- href (redirige) boton que redirige a la pagina de empresa -->
                                <li><a class="dropdown-item" href="#">Nuestro Equipo</a></li>
                                <li><a class="dropdown-item" href="#">Mision</a></li>
                            </ul>
                        </li>                        
                        <li class="nav-item"> <!-- nav-item es para botones simples -->
                            <a class="nav-link" href="servicios.php">Servicios</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="productos.php">Productos</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="contacto.php">Contacto</a>
                        </li>                           
                    </ul>
                </div>  
                <!-- boton de acceso que abre un modal para autenticacion (inicio de sesion) -->
                <button type="button" class="btn btn-outline-primary" data-bs-toggle="modal" data-bs-target="#myModal">Acceder</button>                             
            </div>
        </nav>
        <!--Container (contenido de la pagina)-->
        <div class="container-fluid bg-warning">
            <a href="empresa.php">Ir a Empresa</a><br> <!-- br es para salto de linea -->
            <a href="servicios.php">Ir a Servicios</a><br>
            <a href="productos.php">Ir a Producto</a><br>
            <a href="Contacto.php">Ir a Contacto</a><br>
        </div>
        <!--Footer ( parte de abajo de la pagian )-->
        <div class="container-fluid bg-secondary">
            <div class="row">
                <div class="col-4"></div>
                <div class="col-4" style="color:white"><strong>CookiesandCream@2026</strong></div>
                <div class="col-4"></div>
            </div>
        </div>
        <!--Modal  (ventana emergente)-->
        <div class="modal fade" id="myModal">
            <div class="modal-dialog">
                <div class="modal-content">
                    <!-- Modal Header  -->
                    <div class="modal-header">
                        <h4 class="modal-title">Autentication</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <form action="empresa.php">
                            <div class="mb-3 mt-3">
                                <label for="email" class="form-label">correo electronico:</label>
                                <input type="email" class="form-control" id="email" placeholder="Enter email" name="email">
                            </div>
                            <div class="mb-3">
                                <label for="pwd" class="form-label">contraseña:</label>
                                <input type="password" class="form-control" id="pwd" placeholder="Enter password" name="pswd">
                            </div>
                            <div class="form-check mb-3">
                                <label class="form-check-label">
                                <input class="form-check-input" type="checkbox" name="remember"> Remember me
                                </label>
                            </div>
                            <button type="submit" class="btn btn-primary"> inicio de sesion</button>
                        </form>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Cerrar</button>
                    </div>
                </div>
            </div>
        </div>        
    </body>
</html>