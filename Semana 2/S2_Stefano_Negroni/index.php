<html>
    <head>
        <title>Pagina principal</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>
    </head>
    <body>
        <!--Navbar (barra superior de navegacion)-->

        <nav class="navbar navbar-expand-sm bg-dark navbar-dark">
            <div class="container-fluid">

                <a class="navbar-brand" href="index.php">Logo</a>

                <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                    <span class="navbar-toggler-icon"></span>
                </button>
                <!-- El collapse navbar hace que todos los items se ordenen a la izquierda de manera automatica -->
                <div class="collapse navbar-collapse" id="collapsibleNavbar">
                    <ul class="navbar-nav">

                        <!-- Item en el navbar con menu desplegable -->
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Empresa</a>
                            <ul class="dropdown-menu">
                                <li><a class="dropdown-item" href="empresa.php">Quienes Somos</a></li>
                                <li><a class="dropdown-item" href="#">Nuestro Equipo</a></li>
                                <li><a class="dropdown-item" href="#">Mision</a></li>
                            </ul>
                        </li>

                        <!-- Item simple en navbar -->
                        <li class="nav-item">
                            <a class="nav-link" href="productos.php">Productos</a>
                        </li>

                        <!-- Item simple en navbar -->
                        <li class="nav-item">
                            <a class="nav-link" href="contacto.php">Contacto</a>
                        </li>
                        <!-- Item simple en navbar -->

                        <li class="nav-item">
                            <a class="nav-link" href="ayuda.php">Ayuda</a>
                        </li>
                    </ul>
                </div>
                <!-- Lo que este fuera del collapse navbar se colocara a la derecha del navbar-->
                <button type="button" class="btn btn-success" data-bs-toggle="modal" data-bs-target="#mymodal123">Iniciar Sesion</button>
            </div>
        </nav>

        <!-- Container -->
        <div class="containter-fluid bg-warning">
            <a href="empresa.php">Ir a empresa</a><br>
            <a href="productos.php">Ir a Productos</a><br>
            <a href="contacto.php">Ir a Contacto</a><br>
            <a href="ayuda.php">Ir a Ayuda</a><br>
        </div>

        <!-- Footer (la parte inferior de la pagina)-->
        <div class="container-fluid bg-dark">
            <div class="row">
                <div class="col-4"></div>
                <div class="col-4" style="color:white"><strong>MiEmpresaFantasma@2070</strong></div>
                <div class="col-4"></div>
            </div>
        </div>

        <!-- Modal -->
        <div class="modal fade" id="mymodal123">
            <div class="modal-dialog">
                <div class="modal-content">
                <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Autenticacion</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>

                    <!-- Modal body -->
                    <div class="modal-body">
                        <form action="/action_page.php">
                            <div class="mb-3 mt-3">
                                <label for="email" class="form-label">Email:</label>
                                <input type="email" class="form-control" id="email" placeholder="Ingresar email" name="email">
                            </div>
                            <div class="mb-3">
                                <label for="pwd" class="form-label">Contrasena:</label>
                                <input type="password" class="form-control" id="pwd" placeholder="Ingresar Contrasena" name="pswd">
                            </div>
                                <div class="form-check mb-3">
                                <label class="form-check-label">
                                <input class="form-check-input" type="checkbox" name="remember"> Recordarme
                                </label>
                            </div>
                            <button type="submit" class="btn btn-primary">Iniciar Sesion</button>
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